import os
import logging
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from datetime import datetime

logger = logging.getLogger(__name__)

def generate_payout_receipt(user_name, amount, transaction_id):
    """
    Generates a professional PDF receipt for an MLM commission payout.
    Returns the PDF as a byte stream that can be sent directly to the browser.
    """
    logger.info(f"Generating PDF receipt for {user_name}...")
    
    # Create an in-memory buffer to hold the PDF
    buffer = BytesIO()
    
    # Initialize the PDF Canvas
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # --- Draw Header ---
    p.setFont("Helvetica-Bold", 24)
    p.drawString(50, height - 80, "COMPANY NAME")
    
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 100, "Official Commission Payout Receipt")
    
    # --- Draw Line ---
    p.setStrokeColor(colors.black)
    p.line(50, height - 120, width - 50, height - 120)

    # --- Draw Details ---
    p.setFont("Helvetica", 14)
    y_position = height - 160
    
    details = [
        f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Transaction ID: {transaction_id}",
        f"Pay To: {user_name}",
        f"Amount Transferred: Rs. {amount}"
    ]
    
    for detail in details:
        p.drawString(50, y_position, detail)
        y_position -= 30

    # --- Footer ---
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, 50, "This is a computer-generated document. No signature is required.")

    # Finalize and save the PDF
    p.showPage()
    p.save()

    # Move the buffer cursor to the beginning
    buffer.seek(0)
    return buffer
