# inventory/import_views.py
"""Import functionality for inventory items"""
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
import csv
import io
from typing import List, Dict, Any, Optional
from werkzeug.utils import secure_filename

from utilities.tenant_helpers import tenant_query, tenant_add, tenant_commit, tenant_rollback, get_tenant_session
from middleware.tenant_middleware import tenant_required
from utilities.database import db, Item, Property, PropertyUnit, utc_now
from . import inventory_bp


ALLOWED_EXTENSIONS = {'csv', 'xlsx', 'xls'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_csv_file(file_content: str) -> tuple[List[str], List[Dict[str, str]]]:
    """Parse CSV file and return headers and rows"""
    reader = csv.DictReader(io.StringIO(file_content))
    headers = reader.fieldnames or []
    rows = [row for row in reader]
    return list(headers), rows


def parse_excel_file(file_bytes: bytes) -> tuple[List[str], List[Dict[str, str]]]:
    """Parse Excel file and return headers and rows"""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise ImportError("openpyxl is required for Excel import")

    # Load workbook
    wb = load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    # Get all rows as list
    all_rows = list(ws.iter_rows(values_only=True))

    if not all_rows:
        return [], []

    # First row is headers
    headers = [str(cell) if cell is not None else f"Column_{i}" for i, cell in enumerate(all_rows[0])]

    # Rest are data rows
    rows = []
    for row_data in all_rows[1:]:
        # Convert row to dictionary, handling None values
        row_dict = {}
        for i, cell_value in enumerate(row_data):
            if i < len(headers):
                # Convert to string, handle None and numeric values
                if cell_value is None:
                    row_dict[headers[i]] = ''
                else:
                    row_dict[headers[i]] = str(cell_value)
        rows.append(row_dict)

    wb.close()
    return headers, rows


KEY_FIELDS = {
    'label': {'required': True, 'name': 'Label'},
    'key_hook_number': {'required': False, 'name': 'Key Hook Number'},
    'keycode': {'required': False, 'name': 'Key Code'},
    'total_copies': {'required': False, 'name': 'Total Copies', 'type': 'int'},
    'location': {'required': False, 'name': 'Key Box Location'},
    'address': {'required': False, 'name': 'Address'},
    'status': {'required': False, 'name': 'Status', 'default': 'available'},
    'assigned_to': {'required': False, 'name': 'Assigned To'},
    'property_name': {'required': False, 'name': 'Property Name'},
    'property_unit_label': {'required': False, 'name': 'Property Unit Label'},
}

LOCKBOX_FIELDS = {
    'label': {'required': True, 'name': 'Label'},
    'code_current': {'required': False, 'name': 'Current Code'},
    'code_previous': {'required': False, 'name': 'Previous Code'},
    'supra_id': {'required': False, 'name': 'Supra ID'},
    'location': {'required': False, 'name': 'Location'},
    'address': {'required': False, 'name': 'Address'},
    'status': {'required': False, 'name': 'Status', 'default': 'available'},
    'assigned_to': {'required': False, 'name': 'Assigned To'},
    'property_name': {'required': False, 'name': 'Property Name'},
    'property_unit_label': {'required': False, 'name': 'Property Unit Label'},
}

SIGN_FIELDS = {
    'label': {'required': True, 'name': 'Label'},
    'sign_subtype': {'required': False, 'name': 'Sign Type (Piece/Assembled Unit)'},
    'piece_type': {'required': False, 'name': 'Piece Type'},
    'rider_text': {'required': False, 'name': 'Rider Text'},
    'material': {'required': False, 'name': 'Material'},
    'condition': {'required': False, 'name': 'Condition'},
    'location': {'required': False, 'name': 'Storage Location'},
    'address': {'required': False, 'name': 'Property Address'},
    'status': {'required': False, 'name': 'Status', 'default': 'available'},
    'assigned_to': {'required': False, 'name': 'Assigned To'},
    'property_name': {'required': False, 'name': 'Property Name'},
    'property_unit_label': {'required': False, 'name': 'Property Unit Label'},
}


@inventory_bp.route("/keys/import", methods=["GET", "POST"])
@login_required
@tenant_required
def import_keys():
    """Import keys from CSV/Excel file"""
    if request.method == "POST":
        # Check if file was uploaded
        if 'file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload a CSV or Excel file.", "error")
            return redirect(request.url)

        try:
            # Parse file based on extension
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext == 'csv':
                file_content = file.read().decode('utf-8')
                headers, rows = parse_csv_file(file_content)
            else:  # Excel
                file_bytes = file.read()
                headers, rows = parse_excel_file(file_bytes)

            if not headers or not rows:
                flash("File is empty or could not be parsed", "error")
                return redirect(request.url)

            # Store in session for column mapping
            session['import_data'] = {
                'headers': headers,
                'rows': rows[:100],  # Limit preview to 100 rows
                'total_rows': len(rows),
                'file_type': 'keys'
            }

            return redirect(url_for('inventory.import_keys_map'))

        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")
            return redirect(request.url)

    return render_template("import_upload.html", item_type="Keys")


@inventory_bp.route("/keys/import/map", methods=["GET", "POST"])
@login_required
@tenant_required
def import_keys_map():
    """Map columns from uploaded file to database fields"""
    import_data = session.get('import_data')
    if not import_data:
        flash("No import data found. Please upload a file first.", "error")
        return redirect(url_for('inventory.import_keys'))

    if request.method == "POST":
        # Get column mapping from form
        mapping = {}
        for field_name in KEY_FIELDS.keys():
            column = request.form.get(f'map_{field_name}')
            if column and column != '':
                mapping[field_name] = column

        # Validate required fields
        if 'label' not in mapping:
            flash("Label field is required", "error")
            return redirect(request.url)

        # Store mapping in session
        session['import_mapping'] = mapping
        return redirect(url_for('inventory.import_keys_process'))

    return render_template(
        "import_map.html",
        import_data=import_data,
        fields=KEY_FIELDS,
        item_type="Keys"
    )


@inventory_bp.route("/keys/import/process", methods=["GET", "POST"])
@login_required
@tenant_required
def import_keys_process():
    """Process the import with mapped columns"""
    import_data = session.get('import_data')
    mapping = session.get('import_mapping')

    if not import_data or not mapping:
        flash("Import session expired. Please start over.", "error")
        return redirect(url_for('inventory.import_keys'))

    if request.method == "POST":
        rows = import_data['rows']
        created_count = 0
        error_count = 0
        errors = []

        for idx, row in enumerate(rows, 1):
            try:
                # Extract data using mapping
                label = row.get(mapping.get('label', ''), '').strip()
                if not label:
                    error_count += 1
                    errors.append(f"Row {idx}: Label is required")
                    continue

                # Build item data
                item_data = {'label': label}

                for field_name, config in KEY_FIELDS.items():
                    if field_name == 'label':
                        continue

                    column = mapping.get(field_name)
                    if not column:
                        # Use default if available
                        if 'default' in config:
                            item_data[field_name] = config['default']
                        continue

                    value = row.get(column, '').strip()
                    if not value:
                        if 'default' in config:
                            item_data[field_name] = config['default']
                        continue

                    # Type conversion
                    if config.get('type') == 'int':
                        try:
                            item_data[field_name] = int(value)
                        except ValueError:
                            item_data[field_name] = config.get('default', 0)
                    else:
                        item_data[field_name] = value

                # Handle property lookup
                property_obj = None
                property_unit_obj = None

                property_name = item_data.pop('property_name', None)
                property_unit_label = item_data.pop('property_unit_label', None)

                if property_name:
                    property_obj = tenant_query(Property).filter(
                        Property.name.ilike(property_name)
                    ).first()

                if property_unit_label and property_obj:
                    property_unit_obj = tenant_query(PropertyUnit).filter(
                        PropertyUnit.property_id == property_obj.id,
                        PropertyUnit.label.ilike(property_unit_label)
                    ).first()

                # Create item
                key = Item(
                    type="Key",
                    custom_id=Item.generate_custom_id("Key"),
                    property_id=property_obj.id if property_obj else None,
                    property_unit_id=property_unit_obj.id if property_unit_obj else None,
                    last_action="added",
                    last_action_at=utc_now(),
                    last_action_by_id=current_user.id if current_user.is_authenticated else None,
                    **item_data
                )

                tenant_add(key)
                created_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx}: {str(e)}")

        try:
            tenant_commit()
            flash(f"Successfully imported {created_count} keys", "success")
            if error_count > 0:
                flash(f"{error_count} rows had errors", "warning")

            # Clear session data
            session.pop('import_data', None)
            session.pop('import_mapping', None)

            return redirect(url_for('inventory.list_keys'))

        except Exception as e:
            tenant_rollback()
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('inventory.import_keys'))

    # Show preview
    preview_rows = import_data['rows'][:10]
    preview_data = []

    for row in preview_rows:
        preview_item = {}
        for field_name, column in mapping.items():
            preview_item[field_name] = row.get(column, '')
        preview_data.append(preview_item)

    return render_template(
        "import_preview.html",
        preview_data=preview_data,
        total_rows=import_data['total_rows'],
        fields=KEY_FIELDS,
        mapping=mapping,
        item_type="Keys"
    )


@inventory_bp.route("/lockboxes/import", methods=["GET", "POST"])
@login_required
@tenant_required
def import_lockboxes():
    """Import lockboxes from CSV/Excel file"""
    if request.method == "POST":
        # Check if file was uploaded
        if 'file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload a CSV or Excel file.", "error")
            return redirect(request.url)

        try:
            # Parse file based on extension
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext == 'csv':
                file_content = file.read().decode('utf-8')
                headers, rows = parse_csv_file(file_content)
            else:  # Excel
                file_bytes = file.read()
                headers, rows = parse_excel_file(file_bytes)

            if not headers or not rows:
                flash("File is empty or could not be parsed", "error")
                return redirect(request.url)

            # Store in session for column mapping
            session['import_data'] = {
                'headers': headers,
                'rows': rows[:100],  # Limit preview to 100 rows
                'total_rows': len(rows),
                'file_type': 'lockboxes'
            }

            return redirect(url_for('inventory.import_lockboxes_map'))

        except Exception as e:
            flash(f"Error processing file: {str(e)}", "error")
            return redirect(request.url)

    return render_template("import_upload.html", item_type="Lockboxes")


@inventory_bp.route("/lockboxes/import/map", methods=["GET", "POST"])
@login_required
@tenant_required
def import_lockboxes_map():
    """Map columns from uploaded file to database fields"""
    import_data = session.get('import_data')
    if not import_data:
        flash("No import data found. Please upload a file first.", "error")
        return redirect(url_for('inventory.import_lockboxes'))

    if request.method == "POST":
        # Get column mapping from form
        mapping = {}
        for field_name in LOCKBOX_FIELDS.keys():
            column = request.form.get(f'map_{field_name}')
            if column and column != '':
                mapping[field_name] = column

        # Validate required fields
        if 'label' not in mapping:
            flash("Label field is required", "error")
            return redirect(request.url)

        # Store mapping in session
        session['import_mapping'] = mapping
        return redirect(url_for('inventory.import_lockboxes_process'))

    return render_template(
        "import_map.html",
        import_data=import_data,
        fields=LOCKBOX_FIELDS,
        item_type="Lockboxes"
    )


@inventory_bp.route("/lockboxes/import/process", methods=["GET", "POST"])
@login_required
@tenant_required
def import_lockboxes_process():
    """Process the import with mapped columns"""
    import_data = session.get('import_data')
    mapping = session.get('import_mapping')

    if not import_data or not mapping:
        flash("Import session expired. Please start over.", "error")
        return redirect(url_for('inventory.import_lockboxes'))

    if request.method == "POST":
        rows = import_data['rows']
        created_count = 0
        error_count = 0
        errors = []

        for idx, row in enumerate(rows, 1):
            try:
                # Extract data using mapping
                label = row.get(mapping.get('label', ''), '').strip()
                if not label:
                    error_count += 1
                    errors.append(f"Row {idx}: Label is required")
                    continue

                # Build item data
                item_data = {'label': label}

                for field_name, config in LOCKBOX_FIELDS.items():
                    if field_name == 'label':
                        continue

                    column = mapping.get(field_name)
                    if not column:
                        # Use default if available
                        if 'default' in config:
                            item_data[field_name] = config['default']
                        continue

                    value = row.get(column, '').strip()
                    if not value:
                        if 'default' in config:
                            item_data[field_name] = config['default']
                        continue

                    # Type conversion
                    if config.get('type') == 'int':
                        try:
                            item_data[field_name] = int(value)
                        except ValueError:
                            item_data[field_name] = config.get('default', 0)
                    else:
                        item_data[field_name] = value

                # Handle property lookup
                property_obj = None
                property_unit_obj = None

                property_name = item_data.pop('property_name', None)
                property_unit_label = item_data.pop('property_unit_label', None)

                if property_name:
                    property_obj = tenant_query(Property).filter(
                        Property.name.ilike(property_name)
                    ).first()

                if property_unit_label and property_obj:
                    property_unit_obj = tenant_query(PropertyUnit).filter(
                        PropertyUnit.property_unit_id == property_obj.id,
                        PropertyUnit.label.ilike(property_unit_label)
                    ).first()

                # Create item
                lockbox = Item(
                    type="Lockbox",
                    custom_id=Item.generate_custom_id("Lockbox"),
                    property_id=property_obj.id if property_obj else None,
                    property_unit_id=property_unit_obj.id if property_unit_obj else None,
                    last_action="added",
                    last_action_at=utc_now(),
                    last_action_by_id=current_user.id if current_user.is_authenticated else None,
                    **item_data
                )

                tenant_add(lockbox)
                created_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx}: {str(e)}")

        try:
            tenant_commit()
            flash(f"Successfully imported {created_count} lockboxes", "success")
            if error_count > 0:
                flash(f"{error_count} rows had errors", "warning")

            # Clear session data
            session.pop('import_data', None)
            session.pop('import_mapping', None)

            return redirect(url_for('inventory.list_lockboxes'))

        except Exception as e:
            tenant_rollback()
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('inventory.import_lockboxes'))

    # Show preview
    preview_rows = import_data['rows'][:10]
    preview_data = []

    for row in preview_rows:
        preview_item = {}
        for field_name, column in mapping.items():
            preview_item[field_name] = row.get(column, '')
        preview_data.append(preview_item)

    return render_template(
        "import_preview.html",
        preview_data=preview_data,
        total_rows=import_data['total_rows'],
        fields=LOCKBOX_FIELDS,
        mapping=mapping,
        item_type="Lockboxes"
    )


@inventory_bp.route("/signs/import", methods=["GET", "POST"])
@login_required
@tenant_required
def import_signs():
    """Import signs from CSV/Excel file"""
    if request.method == "POST":
        # Check if file was uploaded
        if 'file' not in request.files:
            flash("No file uploaded", "error")
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(request.url)

        if not allowed_file(file.filename):
            flash("Invalid file type. Please upload a CSV or Excel file.", "error")
            return redirect(request.url)

        try:
            # Parse file based on extension
            filename = secure_filename(file.filename)
            file_ext = filename.rsplit('.', 1)[1].lower()

            if file_ext == 'csv':
                file_content = file.read().decode('utf-8')
                headers, rows = parse_csv_file(file_content)
            else:  # Excel
                file_bytes = file.read()
                headers, rows = parse_excel_file(file_bytes)

            if not headers or not rows:
                flash("File is empty or could not be parsed", "error")
                return redirect(request.url)

            # Store in session
            session['import_data'] = {
                'headers': headers,
                'rows': rows[:1000],  # Limit to first 1000 rows
                'total_rows': len(rows)
            }

            return redirect(url_for('inventory.import_signs_map'))

        except Exception as e:
            flash(f"Error parsing file: {str(e)}", "error")
            return redirect(request.url)

    return render_template("import_upload.html", item_type="Signs")


@inventory_bp.route("/signs/import/map", methods=["GET", "POST"])
@login_required
@tenant_required
def import_signs_map():
    """Map CSV/Excel columns to sign fields"""
    import_data = session.get('import_data')
    if not import_data:
        flash("No import data found. Please upload a file first.", "error")
        return redirect(url_for('inventory.import_signs'))

    if request.method == "POST":
        # Get column mapping from form
        mapping = {}
        for field_name in SIGN_FIELDS.keys():
            column = request.form.get(f'map_{field_name}')
            if column and column != '':
                mapping[field_name] = column

        # Validate required fields
        for field_name, config in SIGN_FIELDS.items():
            if config['required'] and field_name not in mapping:
                flash(f"Please map the required field: {config['name']}", "error")
                return redirect(url_for('inventory.import_signs_map'))

        session['import_mapping'] = mapping
        return redirect(url_for('inventory.import_signs_process'))

    return render_template(
        "import_map.html",
        import_data=import_data,
        fields=SIGN_FIELDS,
        item_type="Signs"
    )


@inventory_bp.route("/signs/import/process", methods=["GET", "POST"])
@login_required
@tenant_required
def import_signs_process():
    """Preview and process sign import"""
    import_data = session.get('import_data')
    mapping = session.get('import_mapping')

    if not import_data or not mapping:
        flash("Missing import data. Please start the import process again.", "error")
        return redirect(url_for('inventory.import_signs'))

    if request.method == "POST":
        # Perform the actual import
        created_count = 0
        skipped_count = 0
        errors = []

        try:
            for idx, row in enumerate(import_data['rows']):
                # Get label (required)
                label_column = mapping.get('label')
                label = str(row.get(label_column, '')).strip() if label_column else ''

                if not label:
                    skipped_count += 1
                    continue

                # Build item data
                item_data = {'label': label}

                for field_name, config in SIGN_FIELDS.items():
                    if field_name == 'label':
                        continue

                    column = mapping.get(field_name)
                    if not column:
                        # Use default if available
                        if 'default' in config:
                            item_data[field_name] = config['default']
                        continue

                    value = str(row.get(column, '')).strip() if row.get(column) is not None else ''
                    if value:
                        item_data[field_name] = value
                    elif 'default' in config:
                        item_data[field_name] = config['default']

                # Handle property and unit mapping
                property_obj = None
                property_unit_obj = None

                property_name = item_data.pop('property_name', None)
                if property_name:
                    property_obj = tenant_query(Property).filter(
                        db.func.lower(Property.name) == property_name.lower()
                    ).first()

                property_unit_label = item_data.pop('property_unit_label', None)
                if property_obj and property_unit_label:
                    property_unit_obj = tenant_query(PropertyUnit).filter(
                        PropertyUnit.property_id == property_obj.id,
                        db.func.lower(PropertyUnit.label) == property_unit_label.lower()
                    ).first()

                # Create sign
                new_sign = Item(
                    type='Sign',
                    **item_data
                )

                if property_obj:
                    new_sign.property_id = property_obj.id
                if property_unit_obj:
                    new_sign.property_unit_id = property_unit_obj.id

                # Generate custom ID
                new_sign.custom_id = Item.generate_custom_id('Sign', item_data.get('sign_subtype'))

                tenant_add(new_sign)
                created_count += 1

            tenant_commit()
            flash(f"Successfully imported {created_count} signs. Skipped {skipped_count} rows.", "success")

            # Clear session data
            session.pop('import_data', None)
            session.pop('import_mapping', None)

            return redirect(url_for('inventory.list_signs'))

        except Exception as e:
            tenant_rollback()
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('inventory.import_signs'))

    # Show preview
    preview_rows = import_data['rows'][:10]
    preview_data = []

    for row in preview_rows:
        preview_item = {}
        for field_name, column in mapping.items():
            preview_item[field_name] = row.get(column, '')
        preview_data.append(preview_item)

    return render_template(
        "import_preview.html",
        preview_data=preview_data,
        total_rows=import_data['total_rows'],
        fields=SIGN_FIELDS,
        mapping=mapping,
        item_type="Signs"
    )
