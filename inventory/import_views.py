# inventory/import_views.py
"""Import functionality for inventory items"""
from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
import csv
import io
from typing import List, Dict, Any, Optional
from werkzeug.utils import secure_filename

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


@inventory_bp.route("/keys/import", methods=["GET", "POST"])
@login_required
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
                    property_obj = Property.query.filter(
                        Property.name.ilike(property_name)
                    ).first()

                if property_unit_label and property_obj:
                    property_unit_obj = PropertyUnit.query.filter(
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

                db.session.add(key)
                created_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {idx}: {str(e)}")

        try:
            db.session.commit()
            flash(f"Successfully imported {created_count} keys", "success")
            if error_count > 0:
                flash(f"{error_count} rows had errors", "warning")

            # Clear session data
            session.pop('import_data', None)
            session.pop('import_mapping', None)

            return redirect(url_for('inventory.list_keys'))

        except Exception as e:
            db.session.rollback()
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
