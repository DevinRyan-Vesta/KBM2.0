# smartlocks/import_views.py
"""Import functionality for smart locks. Mirrors inventory/import_views.py."""
from flask import render_template, request, redirect, url_for, flash, session
from flask_login import login_required
from werkzeug.utils import secure_filename

from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback
from middleware.tenant_middleware import tenant_required
from utilities.database import SmartLock, Property, PropertyUnit
from inventory.import_views import allowed_file, parse_csv_file, parse_excel_file
from . import smartlocks_bp


SMARTLOCK_FIELDS = {
    'label': {'required': True, 'name': 'Label'},
    'code': {'required': True, 'name': 'Code'},
    'provider': {'required': False, 'name': 'Provider'},
    'backup_code': {'required': False, 'name': 'Backup Code'},
    'instructions': {'required': False, 'name': 'Instructions'},
    'notes': {'required': False, 'name': 'Notes'},
    'property_name': {'required': False, 'name': 'Property Name'},
    'property_unit_label': {'required': False, 'name': 'Property Unit Label'},
}


@smartlocks_bp.route("/import", methods=["GET", "POST"])
@login_required
@tenant_required
def import_smartlocks():
    """Upload step — accept a CSV/Excel and stash it in session for mapping."""
    if request.method == "POST":
        if 'file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)

        file = request.files['file']
        if not file.filename:
            flash("No file selected", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload a CSV or Excel file.", "error")
            return redirect(request.url)

        try:
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            if ext == 'csv':
                headers, rows = parse_csv_file(file.read().decode('utf-8'))
            else:
                headers, rows = parse_excel_file(file.read())

            if not headers or not rows:
                flash("File is empty or could not be parsed", "error")
                return redirect(request.url)

            session['import_data'] = {
                'headers': headers,
                'rows': rows[:1000],
                'total_rows': len(rows),
                'file_type': 'smartlocks',
            }
            return redirect(url_for('smartlocks.import_smartlocks_map'))
        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")
            return redirect(request.url)

    return render_template(
        "import_upload.html",
        item_type="SmartLocks",
        restart_url=url_for('smartlocks.import_smartlocks'),
        cancel_url=url_for('smartlocks.list_smartlocks'),
    )


@smartlocks_bp.route("/import/map", methods=["GET", "POST"])
@login_required
@tenant_required
def import_smartlocks_map():
    """Map uploaded columns to SmartLock fields."""
    import_data = session.get('import_data')
    if not import_data or import_data.get('file_type') != 'smartlocks':
        flash("No import data found. Please upload a file first.", "error")
        return redirect(url_for('smartlocks.import_smartlocks'))

    if request.method == "POST":
        mapping = {}
        for field_name in SMARTLOCK_FIELDS:
            column = request.form.get(f'map_{field_name}')
            if column:
                mapping[field_name] = column

        for field_name, config in SMARTLOCK_FIELDS.items():
            if config['required'] and field_name not in mapping:
                flash(f"Please map the required field: {config['name']}", "error")
                return redirect(request.url)

        session['import_mapping'] = mapping
        return redirect(url_for('smartlocks.import_smartlocks_process'))

    return render_template(
        "import_map.html",
        import_data=import_data,
        fields=SMARTLOCK_FIELDS,
        item_type="SmartLocks",
        restart_url=url_for('smartlocks.import_smartlocks'),
    )


@smartlocks_bp.route("/import/process", methods=["GET", "POST"])
@login_required
@tenant_required
def import_smartlocks_process():
    """Preview, then commit, the mapped smart-lock import."""
    import_data = session.get('import_data')
    mapping = session.get('import_mapping')

    if not import_data or not mapping or import_data.get('file_type') != 'smartlocks':
        flash("Import session expired. Please start over.", "error")
        return redirect(url_for('smartlocks.import_smartlocks'))

    if request.method == "POST":
        rows = import_data['rows']
        created_count = 0
        error_count = 0
        errors = []

        for idx, row in enumerate(rows, 1):
            try:
                label = (row.get(mapping.get('label', '')) or '').strip()
                code = (row.get(mapping.get('code', '')) or '').strip()
                if not label:
                    error_count += 1
                    errors.append(f"Row {idx}: Label is required")
                    continue
                if not code:
                    error_count += 1
                    errors.append(f"Row {idx}: Code is required")
                    continue

                lock_data = {'label': label, 'code': code}
                for field_name in ('provider', 'backup_code', 'instructions', 'notes'):
                    column = mapping.get(field_name)
                    if column:
                        value = (row.get(column) or '').strip()
                        if value:
                            lock_data[field_name] = value

                property_obj = None
                property_unit_obj = None
                property_name = (row.get(mapping.get('property_name', '')) or '').strip()
                property_unit_label = (row.get(mapping.get('property_unit_label', '')) or '').strip()

                if property_name:
                    property_obj = tenant_query(Property).filter(
                        Property.name.ilike(property_name)
                    ).first()

                if property_obj and property_unit_label:
                    property_unit_obj = tenant_query(PropertyUnit).filter(
                        PropertyUnit.property_id == property_obj.id,
                        PropertyUnit.label.ilike(property_unit_label),
                    ).first()

                lock = SmartLock(
                    property_id=property_obj.id if property_obj else None,
                    property_unit_id=property_unit_obj.id if property_unit_obj else None,
                    **lock_data,
                )
                tenant_add(lock)
                created_count += 1
            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx}: {str(e)}")

        try:
            tenant_commit()
            flash(f"Successfully imported {created_count} smart locks.", "success")
            if error_count:
                flash(f"{error_count} rows had errors.", "warning")
            session.pop('import_data', None)
            session.pop('import_mapping', None)
            return redirect(url_for('smartlocks.list_smartlocks'))
        except Exception as e:
            tenant_rollback()
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('smartlocks.import_smartlocks'))

    preview_rows = import_data['rows'][:10]
    preview_data = []
    for row in preview_rows:
        preview_item = {field: row.get(column, '') for field, column in mapping.items()}
        preview_data.append(preview_item)

    return render_template(
        "import_preview.html",
        preview_data=preview_data,
        total_rows=import_data['total_rows'],
        fields=SMARTLOCK_FIELDS,
        mapping=mapping,
        item_type="SmartLocks",
        restart_url=url_for('smartlocks.import_smartlocks'),
        back_url=url_for('smartlocks.import_smartlocks_map'),
    )
