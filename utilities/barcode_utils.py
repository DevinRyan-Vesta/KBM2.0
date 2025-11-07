"""
Barcode and QR Code generation utilities for inventory items.

This module provides functions to generate QR codes and barcodes for inventory
items, enabling quick identification and checkout via scanning.
"""
import qrcode
import barcode
from barcode.writer import ImageWriter
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from typing import List, Dict, Tuple, Optional
import os


class BarcodeGenerator:
    """Handles generation of barcodes and QR codes for inventory items."""

    def __init__(self, base_url: str = None):
        """
        Initialize the barcode generator.

        Args:
            base_url: Base URL for the application (e.g., https://yourdomain.com)
        """
        self.base_url = base_url or os.environ.get('APP_BASE_URL', 'http://localhost:5000')

    def generate_qr_code(
        self,
        item_id: int,
        item_type: str,
        label: str,
        custom_id: str = None,
        size: int = 10,
        border: int = 2
    ) -> BytesIO:
        """
        Generate a QR code for an inventory item.

        Args:
            item_id: Database ID of the item
            item_type: Type of item (key, lockbox, sign, smartlock)
            label: Display label for the item
            custom_id: Optional custom ID/barcode for the item
            size: Size of the QR code (default 10)
            border: Border size in boxes (default 2)

        Returns:
            BytesIO object containing the QR code image
        """
        # Create URL to item details page
        item_url = f"{self.base_url}/inventory/item/{item_id}"

        # Create QR code data
        qr_data = {
            'id': item_id,
            'type': item_type,
            'label': label,
            'url': item_url
        }

        if custom_id:
            qr_data['custom_id'] = custom_id

        # Format data for QR code
        qr_text = f"KBM-{item_type.upper()}\nID: {item_id}\nLabel: {label}\n{item_url}"

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,  # Auto-size
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=border,
        )
        qr.add_data(qr_text)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    def generate_barcode(
        self,
        code: str,
        barcode_type: str = 'code128',
        add_checksum: bool = True
    ) -> BytesIO:
        """
        Generate a 1D barcode.

        Args:
            code: The code to encode
            barcode_type: Type of barcode (code128, code39, ean13, etc.)
            add_checksum: Whether to add a checksum

        Returns:
            BytesIO object containing the barcode image
        """
        # Get barcode class
        barcode_class = barcode.get_barcode_class(barcode_type)

        # Generate barcode
        buffer = BytesIO()
        code_obj = barcode_class(code, writer=ImageWriter(), add_checksum=add_checksum)
        code_obj.write(buffer)
        buffer.seek(0)

        return buffer

    def create_label_image(
        self,
        item_id: int,
        item_type: str,
        label: str,
        custom_id: str = None,
        width: int = 400,
        height: int = 300
    ) -> BytesIO:
        """
        Create a complete label image with QR code and text information.

        Args:
            item_id: Database ID of the item
            item_type: Type of item
            label: Display label
            custom_id: Optional custom ID
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            BytesIO object containing the label image
        """
        # Create blank image
        img = Image.new('RGB', (width, height), 'white')
        draw = ImageDraw.Draw(img)

        # Try to load a font, fallback to default if not available
        try:
            title_font = ImageFont.truetype("arial.ttf", 20)
            text_font = ImageFont.truetype("arial.ttf", 14)
            small_font = ImageFont.truetype("arial.ttf", 10)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Generate QR code
        qr_buffer = self.generate_qr_code(item_id, item_type, label, custom_id, size=5, border=1)
        qr_img = Image.open(qr_buffer)

        # Calculate QR code position (centered on left side)
        qr_size = min(height - 20, width // 2)
        qr_img = qr_img.resize((qr_size, qr_size))
        qr_x = 10
        qr_y = (height - qr_size) // 2

        # Paste QR code
        img.paste(qr_img, (qr_x, qr_y))

        # Add text information on the right side
        text_x = qr_x + qr_size + 20
        text_y = 20

        # Draw title
        draw.text((text_x, text_y), f"{item_type.upper()}", fill='black', font=title_font)
        text_y += 30

        # Draw label
        draw.text((text_x, text_y), f"Label:", fill='gray', font=small_font)
        text_y += 15
        draw.text((text_x, text_y), label[:30], fill='black', font=text_font)
        text_y += 25

        # Draw ID
        draw.text((text_x, text_y), f"ID: {item_id}", fill='gray', font=small_font)
        text_y += 20

        # Draw custom ID if available
        if custom_id:
            draw.text((text_x, text_y), f"Custom ID:", fill='gray', font=small_font)
            text_y += 15
            draw.text((text_x, text_y), custom_id[:30], fill='black', font=text_font)
            text_y += 25

        # Draw scan instruction
        text_y = height - 40
        draw.text((text_x, text_y), "Scan QR code to view", fill='gray', font=small_font)
        text_y += 12
        draw.text((text_x, text_y), "item details", fill='gray', font=small_font)

        # Save to buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        return buffer

    def create_labels_pdf(
        self,
        items: List[Dict],
        columns: int = 2,
        rows: int = 4
    ) -> BytesIO:
        """
        Create a PDF with multiple item labels for printing.

        Args:
            items: List of dicts with keys: id, type, label, custom_id (optional)
            columns: Number of labels per row
            rows: Number of rows per page

        Returns:
            BytesIO object containing the PDF
        """
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        page_width, page_height = letter

        # Calculate label dimensions
        margin = 0.25 * inch
        spacing = 0.1 * inch
        label_width = (page_width - 2 * margin - (columns - 1) * spacing) / columns
        label_height = (page_height - 2 * margin - (rows - 1) * spacing) / rows

        labels_per_page = columns * rows
        total_items = len(items)

        for page_num in range((total_items + labels_per_page - 1) // labels_per_page):
            if page_num > 0:
                c.showPage()

            start_idx = page_num * labels_per_page
            end_idx = min(start_idx + labels_per_page, total_items)

            for idx in range(start_idx, end_idx):
                item = items[idx]
                local_idx = idx - start_idx

                # Calculate position
                col = local_idx % columns
                row = local_idx // columns

                x = margin + col * (label_width + spacing)
                y = page_height - margin - (row + 1) * label_height - row * spacing

                # Generate label image
                label_img_buffer = self.create_label_image(
                    item_id=item['id'],
                    item_type=item['type'],
                    label=item['label'],
                    custom_id=item.get('custom_id'),
                    width=int(label_width * 2),  # Higher resolution
                    height=int(label_height * 2)
                )

                # Draw image on PDF
                img_reader = ImageReader(label_img_buffer)
                c.drawImage(
                    img_reader,
                    x, y,
                    width=label_width,
                    height=label_height,
                    preserveAspectRatio=True
                )

                # Draw border around label
                c.rect(x, y, label_width, label_height)

        c.save()
        buffer.seek(0)
        return buffer

    def create_single_label_pdf(
        self,
        item_id: int,
        item_type: str,
        label: str,
        custom_id: str = None
    ) -> BytesIO:
        """
        Create a single-page PDF with one large label.

        Args:
            item_id: Database ID of the item
            item_type: Type of item
            label: Display label
            custom_id: Optional custom ID

        Returns:
            BytesIO object containing the PDF
        """
        return self.create_labels_pdf(
            items=[{
                'id': item_id,
                'type': item_type,
                'label': label,
                'custom_id': custom_id
            }],
            columns=1,
            rows=1
        )


# Global instance
barcode_generator = BarcodeGenerator()
