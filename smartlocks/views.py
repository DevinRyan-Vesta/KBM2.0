import logging
import os
import uuid
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, abort,
    send_from_directory, current_app, g,
)
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from utilities.tenant_helpers import (
    tenant_query, tenant_add, tenant_commit, tenant_rollback, tenant_delete, get_tenant_session,
)
from middleware.tenant_middleware import tenant_required
from utilities.database import db, SmartLock, SmartLockImage, Property, PropertyUnit, log_activity

log = logging.getLogger(__name__)

smartlocks_bp = Blueprint(
    "smartlocks",
    __name__,
    template_folder="../templates",
    static_folder="../static",
)


# ---------------------------------------------------------------------------
# Image upload constraints + helpers
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MiB per image


def _uploads_root() -> Path:
    """Filesystem root for tenant-scoped uploads. Created lazily."""
    base = Path(current_app.root_path) / "uploads"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _smartlock_upload_dir(lock: SmartLock) -> Path:
    """Per-tenant, per-lock upload directory. Tenant subdomain in the path
    keeps things visibly separated on disk; the actual access control is
    the tenant context check at serve time."""
    tenant = g.get("tenant")
    if tenant is None:
        abort(404)
    subdir = _uploads_root() / tenant.subdomain / "smartlocks" / str(lock.id)
    subdir.mkdir(parents=True, exist_ok=True)
    return subdir


def _ext_of(filename: str) -> str:
    return filename.rsplit(".", 1)[1].lower() if "." in filename else ""


def _looks_like_an_image(file_storage) -> bool:
    """Verify the uploaded file is actually an image, not just a renamed
    text file. Reads the file header via Pillow and rejects if parsing fails."""
    try:
        from PIL import Image
        pos = file_storage.stream.tell()
        try:
            with Image.open(file_storage.stream) as img:
                img.verify()
            return True
        finally:
            file_storage.stream.seek(pos)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def _get_smartlock_or_404(lock_id: int) -> SmartLock:
    smart_lock = get_tenant_session().get(SmartLock, lock_id)
    if smart_lock is None:
        abort(404)
    return smart_lock


def _resolve_property_and_unit(property_id_str: str, unit_id_str: str):
    """Returns (property_obj, unit_obj, error_messages). Either object can
    be None — both fields are optional on the form."""
    errors: list[str] = []
    property_ref = None
    if property_id_str:
        try:
            property_ref = get_tenant_session().get(Property, int(property_id_str))
        except ValueError:
            property_ref = None
        if property_ref is None:
            errors.append("Selected property could not be found.")

    unit_ref = None
    if unit_id_str:
        try:
            unit_ref = get_tenant_session().get(PropertyUnit, int(unit_id_str))
        except ValueError:
            unit_ref = None
        if unit_ref is None:
            errors.append("Selected unit could not be found.")
    return property_ref, unit_ref, errors


def _form_str(name: str) -> str | None:
    """Pull a stripped form value, returning None when empty (so we store
    NULL instead of empty strings on optional fields)."""
    raw = (request.form.get(name) or "").strip()
    return raw or None


def _apply_smartlock_form(lock: SmartLock):
    """Copy form fields onto a SmartLock instance. Caller is responsible
    for required-field validation and committing the session."""
    lock.label = (request.form.get("label") or "").strip() or lock.label
    lock.code = (request.form.get("code") or "").strip() or lock.code
    lock.provider = _form_str("provider")
    lock.backup_code = _form_str("backup_code")
    lock.instructions = _form_str("instructions")
    lock.notes = _form_str("notes")
    lock.model_number = _form_str("model_number")
    lock.serial_number = _form_str("serial_number")
    lock.pairing_code = _form_str("pairing_code")
    lock.qr_code_data = _form_str("qr_code_data")


# ---------------------------------------------------------------------------
# CRUD routes
# ---------------------------------------------------------------------------

@smartlocks_bp.route("/", methods=["GET"])
@login_required
@tenant_required
def list_smartlocks():
    q = (request.args.get("q") or "").strip()
    query = tenant_query(SmartLock)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                SmartLock.label.ilike(like),
                SmartLock.code.ilike(like),
                SmartLock.provider.ilike(like),
                SmartLock.model_number.ilike(like),
                SmartLock.serial_number.ilike(like),
            )
        )
    locks = query.order_by(SmartLock.label.asc()).all()
    return render_template("smartlocks.html", smartlocks=locks, q=q)


@smartlocks_bp.route("/new", methods=["GET", "POST"])
@login_required
@tenant_required
def create_smartlock():
    properties = tenant_query(Property).order_by(Property.name.asc()).all()
    property_units = tenant_query(PropertyUnit).order_by(PropertyUnit.label.asc()).all()

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        code = (request.form.get("code") or "").strip()

        errors: list[str] = []
        if not label:
            errors.append("Label is required.")
        if not code:
            errors.append("Code is required.")

        property_ref, unit_ref, prop_errors = _resolve_property_and_unit(
            (request.form.get("property_id") or "").strip(),
            (request.form.get("property_unit_id") or "").strip(),
        )
        errors.extend(prop_errors)

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("smartlocks.create_smartlock"))

        smart_lock = SmartLock(label=label, code=code)
        _apply_smartlock_form(smart_lock)
        smart_lock.property = property_ref
        smart_lock.property_unit = unit_ref

        tenant_add(smart_lock)
        tenant_commit()
        flash("Smart lock saved.", "success")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=smart_lock.id))

    return render_template(
        "smartlock_form.html",
        smartlock=None,
        properties=properties,
        property_units=property_units,
        form_action=url_for("smartlocks.create_smartlock"),
        page_title="Add Smart Lock",
        submit_label="Save Smart Lock",
    )


@smartlocks_bp.route("/<int:lock_id>", methods=["GET"])
@login_required
@tenant_required
def smartlock_detail(lock_id: int):
    smart_lock = _get_smartlock_or_404(lock_id)
    return render_template("smartlock_detail.html", smartlock=smart_lock)


@smartlocks_bp.route("/<int:lock_id>/edit", methods=["GET", "POST"])
@login_required
@tenant_required
def edit_smartlock(lock_id: int):
    smart_lock = _get_smartlock_or_404(lock_id)
    properties = tenant_query(Property).order_by(Property.name.asc()).all()
    property_units = tenant_query(PropertyUnit).order_by(PropertyUnit.label.asc()).all()

    if request.method == "POST":
        label = (request.form.get("label") or "").strip()
        code = (request.form.get("code") or "").strip()

        errors: list[str] = []
        if not label:
            errors.append("Label is required.")
        if not code:
            errors.append("Code is required.")

        property_ref, unit_ref, prop_errors = _resolve_property_and_unit(
            (request.form.get("property_id") or "").strip(),
            (request.form.get("property_unit_id") or "").strip(),
        )
        errors.extend(prop_errors)

        if errors:
            for message in errors:
                flash(message, "error")
            return redirect(url_for("smartlocks.edit_smartlock", lock_id=lock_id))

        _apply_smartlock_form(smart_lock)
        smart_lock.property = property_ref
        smart_lock.property_unit = unit_ref

        tenant_commit()
        flash("Smart lock updated.", "success")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    return render_template(
        "smartlock_form.html",
        smartlock=smart_lock,
        properties=properties,
        property_units=property_units,
        form_action=url_for("smartlocks.edit_smartlock", lock_id=lock_id),
        page_title=f"Edit {smart_lock.label}",
        submit_label="Save Changes",
    )


@smartlocks_bp.route("/<int:lock_id>/delete", methods=["POST"])
@login_required
@tenant_required
def delete_smartlock(lock_id: int):
    smart_lock = _get_smartlock_or_404(lock_id)
    label = smart_lock.label

    # Best-effort cleanup of on-disk image files. SmartLockImage rows are
    # cascade-deleted via the ORM relationship.
    try:
        upload_dir = _smartlock_upload_dir(smart_lock)
        for image in smart_lock.images:
            file_path = upload_dir / image.filename
            if file_path.exists():
                file_path.unlink()
        try:
            upload_dir.rmdir()
        except OSError:
            pass  # not empty, leave it
    except Exception:
        log.exception("smartlock %s: failed to clean up upload dir during delete", lock_id)

    tenant_delete(smart_lock)
    tenant_commit()
    flash(f'Smart lock "{label}" deleted.', "success")
    return redirect(url_for("smartlocks.list_smartlocks"))


# ---------------------------------------------------------------------------
# Image routes
# ---------------------------------------------------------------------------

@smartlocks_bp.route("/<int:lock_id>/images/upload", methods=["POST"])
@login_required
@tenant_required
def upload_smartlock_image(lock_id: int):
    """Accept one image file + optional caption, store on disk + DB row."""
    smart_lock = _get_smartlock_or_404(lock_id)

    file = request.files.get("image")
    caption = (request.form.get("caption") or "").strip() or None

    if not file or not file.filename:
        flash("Choose a file to upload.", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    ext = _ext_of(secure_filename(file.filename))
    if ext not in ALLOWED_IMAGE_EXTS:
        flash(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTS))}", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    if file.mimetype and file.mimetype not in ALLOWED_IMAGE_MIMES:
        flash(f"Unsupported image type: {file.mimetype}", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size <= 0:
        flash("Uploaded file is empty.", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))
    if size > MAX_IMAGE_BYTES:
        mb = MAX_IMAGE_BYTES // (1024 * 1024)
        flash(f"File too large ({size // 1024 // 1024} MiB). Limit is {mb} MiB.", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    if not _looks_like_an_image(file):
        flash("That file doesn't look like a valid image.", "error")
        return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = _smartlock_upload_dir(smart_lock)
    target = upload_dir / stored_name
    file.save(str(target))

    record = SmartLockImage(
        smart_lock_id=smart_lock.id,
        filename=stored_name,
        original_filename=secure_filename(file.filename),
        caption=caption,
        content_type=file.mimetype,
        size_bytes=size,
        uploaded_by_id=getattr(current_user, "id", None),
    )
    tenant_add(record)
    tenant_commit()

    flash("Image uploaded.", "success")
    return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))


@smartlocks_bp.route("/<int:lock_id>/images/<int:image_id>", methods=["GET"])
@login_required
@tenant_required
def serve_smartlock_image(lock_id: int, image_id: int):
    """Serve an image file. Tenant-scoped: the request must be on the
    tenant's subdomain (enforced by @tenant_required) AND the image must
    belong to a smart lock in this tenant's DB."""
    smart_lock = _get_smartlock_or_404(lock_id)
    image = get_tenant_session().get(SmartLockImage, image_id)
    if image is None or image.smart_lock_id != smart_lock.id:
        abort(404)

    upload_dir = _smartlock_upload_dir(smart_lock)
    if not (upload_dir / image.filename).exists():
        abort(404)

    return send_from_directory(
        upload_dir,
        image.filename,
        download_name=image.original_filename or image.filename,
        as_attachment=False,
    )


@smartlocks_bp.route("/<int:lock_id>/images/<int:image_id>/delete", methods=["POST"])
@login_required
@tenant_required
def delete_smartlock_image(lock_id: int, image_id: int):
    smart_lock = _get_smartlock_or_404(lock_id)
    image = get_tenant_session().get(SmartLockImage, image_id)
    if image is None or image.smart_lock_id != smart_lock.id:
        abort(404)

    try:
        file_path = _smartlock_upload_dir(smart_lock) / image.filename
        if file_path.exists():
            file_path.unlink()
    except Exception:
        log.exception("smartlock image %s: failed to delete file", image_id)

    tenant_delete(image)
    tenant_commit()
    flash("Image deleted.", "success")
    return redirect(url_for("smartlocks.smartlock_detail", lock_id=lock_id))


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@smartlocks_bp.route("/export", methods=["GET"])
@login_required
@tenant_required
def export_smartlocks():
    """Export smart locks (filtered by current search) as CSV or Excel."""
    from exports.views import generate_csv, generate_excel
    from datetime import datetime

    q = (request.args.get("q") or "").strip()
    format_type = (request.args.get("format") or "csv").lower()

    query = tenant_query(SmartLock)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                SmartLock.label.ilike(like),
                SmartLock.code.ilike(like),
                SmartLock.provider.ilike(like),
                SmartLock.model_number.ilike(like),
                SmartLock.serial_number.ilike(like),
            )
        )
    locks = query.order_by(SmartLock.label.asc()).all()

    data = []
    for lock in locks:
        data.append({
            "Label": lock.label or "",
            "Code": lock.code or "",
            "Provider": lock.provider or "",
            "Backup Code": lock.backup_code or "",
            "Model Number": lock.model_number or "",
            "Serial Number": lock.serial_number or "",
            "Pairing Code": lock.pairing_code or "",
            "QR Code Data": lock.qr_code_data or "",
            "Instructions": lock.instructions or "",
            "Notes": lock.notes or "",
            "Property": lock.property.name if lock.property else "",
            "Unit": lock.property_unit.label if lock.property_unit else "",
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if format_type == "excel":
        return generate_excel(data, f"smartlocks_{timestamp}.xlsx")
    return generate_csv(data, f"smartlocks_{timestamp}.csv")
