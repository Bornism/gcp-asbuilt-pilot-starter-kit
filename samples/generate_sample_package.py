#!/usr/bin/env python3
"""
Synthetic As-Built PDF Package Generator
========================================
Generates a realistic 3-page utility drawing package PDF:
- Page 1: Cover Sheet with Title Block and Unsigned P.E. Stamp Box (triggers Check #2 FAIL)
- Page 2: Plan View CAD Layout with 425 LF Conduit Redline Callout
- Page 3: Bill of Materials (BOM) Table billing only 380 LF Conduit (triggers Check #8 FAIL)

Used to test the starter kit locally or in Argolis without needing proprietary customer blueprints.
"""

import os
from pypdf import PdfWriter
from reportlab.lib.pagesizes import letter, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors


def create_synthetic_asbuilt_pdf(output_path: str = "samples/sample_job_package_wo440219.pdf"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=landscape(letter))
    width, height = landscape(letter)

    # -------------------------------------------------------------------------
    # PAGE 1: COVER SHEET & TITLE BLOCK (Defect: Missing P.E. Stamp)
    # -------------------------------------------------------------------------
    # Border
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(2)
    c.rect(20, 20, width - 40, height - 40)

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(40, height - 60, "PACIFIC UTILITY DISTRIBUTION - AS-BUILT RECORD DRAWINGS")
    c.setFont("Helvetica", 12)
    c.setFillColor(colors.HexColor("#475569"))
    c.drawString(40, height - 80, "ELECTRIC DISTRIBUTION RELIABILITY & UNDERGROUND HARDENING PROJECT")

    # Sheet Index Box
    c.rect(40, height - 250, 320, 140)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 130, "DRAWING SHEET INDEX")
    c.setFont("Helvetica", 9)
    c.drawString(50, height - 155, "Sheet 1 of 3: Cover Sheet & Professional Certifications (Rev 1)")
    c.drawString(50, height - 175, "Sheet 2 of 3: Civil & Underground Conduit Plan View (Rev 2)")
    c.drawString(50, height - 195, "Sheet 3 of 3: Construction Bill of Materials & Equipment Tally (Rev 1)")

    # As-Built Stamp (PASS)
    c.setStrokeColor(colors.HexColor("#DC2626"))
    c.setLineWidth(2)
    c.rect(40, 50, 240, 90)
    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 115, "OFFICIAL AS-BUILT RECORD")
    c.setFont("Helvetica", 9)
    c.drawString(50, 95, "Verified by Foreman: J. Martinez")
    c.drawString(50, 80, "Field Completion Date: 08/23/2026")
    c.drawString(50, 65, "Status: Field Construction Complete")

    # California P.E. Stamp Box (DEFECT: Blank / Unsigned -> Triggers Rule #2 FAIL)
    c.setStrokeColor(colors.HexColor("#64748B"))
    c.setLineWidth(1)
    c.rect(300, 50, 180, 110)
    c.setFillColor(colors.HexColor("#94A3B8"))
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(390, 140, "STATE OF CALIFORNIA")
    c.drawCentredString(390, 125, "PROFESSIONAL ENGINEER (P.E.) SEAL")
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColor(colors.HexColor("#EF4444"))
    c.drawCentredString(390, 95, "[ SPACE UNSTAMPED ]")
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#64748B"))
    c.drawCentredString(390, 70, "Signature & Digital Seal Required")

    # Title Block (Bottom Right)
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.5)
    c.rect(width - 260, 20, 240, 140)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(width - 250, 140, "CONTRACTOR: CONTRACTOR UTILITY ENGINEERING")
    c.setFont("Helvetica", 9)
    c.drawString(width - 250, 120, "Work Order: WO-440219-FRESNO")
    c.drawString(width - 250, 100, "Job Package ID: MP-2026-08819")
    c.drawString(width - 250, 80, "Location: Fresno Division, CA")
    c.drawString(width - 250, 60, "Date: 08/25/2026")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 250, 35, "DRAWING: Sheet 1 of 3 (Cover)")

    c.showPage()

    # -------------------------------------------------------------------------
    # PAGE 2: PLAN VIEW CAD DRAWING (Defect: 425 LF Plan Conduit)
    # -------------------------------------------------------------------------
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(2)
    c.rect(20, 20, width - 40, height - 40)

    # North Arrow
    c.setStrokeColor(colors.HexColor("#0F172A"))
    c.line(width - 80, height - 60, width - 80, height - 100)
    c.polygon([(width - 80, height - 55), (width - 86, height - 70), (width - 74, height - 70)], fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 83, height - 50, "N")

    # Drawing Title
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(40, height - 60, "UNDERGROUND DISTRIBUTION & CONDUIT ALIGNMENT PLAN")
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 75, "E. Shaw Avenue from N. Fresno St to Pole 1A | Scale: 1\" = 40'")

    # Schematic linework
    c.setStrokeColor(colors.HexColor("#DC2626"))  # REDLINE
    c.setLineWidth(3)
    c.line(100, height - 180, 450, height - 180)
    c.line(450, height - 180, 450, height - 280)

    # Asset Callouts
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(70, height - 170, "Existing Pole #1A")
    c.drawString(420, height - 300, "New Vault V-12")

    # Redline Conduit Callout (425 LF)
    c.setFillColor(colors.HexColor("#DC2626"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(180, height - 165, "FIELD REDLINE: 425 LF OF 4-INCH SCH 40 PVC CONDUIT")
    c.setFont("Helvetica", 9)
    c.drawString(180, height - 200, "Trench Depth: 42\" cover (Exceeds CPUC GO 128)")

    # USA 811 Ticket Notice (PASS)
    c.setStrokeColor(colors.HexColor("#2563EB"))
    c.rect(40, 50, 260, 60)
    c.setFillColor(colors.HexColor("#1E3A8A"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, 95, "UNDERGROUND SERVICE ALERT (USA 811)")
    c.setFont("Helvetica", 8)
    c.drawString(50, 80, "Ticket #0429184 | Certified Valid")
    c.drawString(50, 65, "Subsurface utilities marked prior to trench excavation.")

    # Title Block
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.5)
    c.rect(width - 260, 20, 240, 100)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(width - 250, 100, "Work Order: WO-440219-FRESNO")
    c.drawString(width - 250, 80, "Job ID: MP-2026-08819")
    c.drawString(width - 250, 60, "Revision: Rev 2 (Redline Field Changes)")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 250, 35, "DRAWING: Sheet 2 of 3 (Plan View)")

    c.showPage()

    # -------------------------------------------------------------------------
    # PAGE 3: BILL OF MATERIALS (BOM) (Defect: 380 LF Billed -> Triggers Check #8 FAIL)
    # -------------------------------------------------------------------------
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(2)
    c.rect(20, 20, width - 40, height - 40)

    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(40, height - 60, "CONSTRUCTION BILL OF MATERIALS & INSTALLED MATERIAL TALLY")
    c.setFont("Helvetica", 9)
    c.drawString(40, height - 75, "Reconciliation Table for Work Order: WO-440219-FRESNO")

    # Table Header
    y = height - 120
    c.setFillColor(colors.HexColor("#1E293B"))
    c.rect(40, y, width - 80, 25, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, y + 8, "Item #")
    c.drawString(100, y + 8, "Utility Stock Code")
    c.drawString(220, y + 8, "Description")
    c.drawString(440, y + 8, "Unit")
    c.drawString(500, y + 8, "Design Qty")
    c.drawString(580, y + 8, "Final Billed Qty (As-Built)")

    # Rows
    rows = [
        ("01", "029410", "4-inch Schedule 40 PVC Conduit", "LF", "400", "380"),  # MISMATCH (-45 LF against 425 LF plan!)
        ("02", "018442", "Precast Concrete Utility Vault 4'x6'", "EA", "1", "1"),
        ("03", "053819", "50 kVA Overhead Transformer 120/240V", "EA", "1", "1"),
        ("04", "088121", "#4/0 AWG Triplex Secondary Aluminum", "LF", "450", "450"),
        ("05", "033104", "5/8\" x 8' Copper Clad Ground Rod", "EA", "4", "4")
    ]

    c.setFillColor(colors.HexColor("#0F172A"))
    c.setFont("Helvetica", 9)
    for idx, (it, code, desc, unit, dqty, bqty) in enumerate(rows):
        y -= 25
        if idx % 2 == 1:
            c.setFillColor(colors.HexColor("#F1F5F9"))
            c.rect(40, y - 5, width - 80, 25, fill=1)
            c.setFillColor(colors.HexColor("#0F172A"))

        # Highlight conduit row
        if it == "01":
            c.setFillColor(colors.HexColor("#DC2626"))
            c.setFont("Helvetica-Bold", 9)
        else:
            c.setFillColor(colors.HexColor("#0F172A"))
            c.setFont("Helvetica", 9)

        c.drawString(50, y + 4, it)
        c.drawString(100, y + 4, code)
        c.drawString(220, y + 4, desc)
        c.drawString(440, y + 4, unit)
        c.drawString(500, y + 4, dqty)
        c.drawString(580, y + 4, bqty)

    # Title Block
    c.setStrokeColor(colors.HexColor("#1E293B"))
    c.setLineWidth(1.5)
    c.rect(width - 260, 20, 240, 100)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#0F172A"))
    c.drawString(width - 250, 100, "Work Order: WO-440219-FRESNO")
    c.drawString(width - 250, 80, "Job ID: MP-2026-08819")
    c.drawString(width - 250, 60, "Revision: Rev 1")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(width - 250, 35, "DRAWING: Sheet 3 of 3 (BOM Tally)")

    c.showPage()
    c.save()
    print(f"Generated synthetic As-Built package PDF: {output_path}")


if __name__ == "__main__":
    create_synthetic_asbuilt_pdf()
