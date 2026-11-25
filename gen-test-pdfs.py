#!/usr/bin/env python3
"""Generate 5 digital test invoices (PDF) for the AI Supplier Invoice Auditor.
Supplier: City Foods Wholesale. Buyer: Spice House Restaurant.
All maths verified by hand; see invoice-auditor-TESTS.md for expectations.

A INV-2501 23 Nov 2026 - CLEAN (all maths right, all prices at agreed rates)
B INV-2502 24 Nov 2026 (Tuesday) - OVERCHARGED $42.00 (tomatoes $4.20 vs $3.50 agreed, 60 kg)
C INV-2503 24 Nov 2026 - MATH ERROR (chicken line stated $86.00, should be $68.00)
D INV-2504 25 Nov 2026 - FLAGGED (saffron has no agreed rate)
E INV-2505 25 Nov 2026 - OVERCHARGED $87.50 (tomatoes billed twice)
"""
from fpdf import FPDF
import os

OUT = os.path.dirname(os.path.abspath(__file__)) + "/tests"

def make_pdf(fname, inv_no, date, due, lines, subtotal, tax, grand):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 10, "CITY FOODS WHOLESALE", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Wholesale Food Supplier - 14 Market Road, Peshawar", ln=True)
    pdf.cell(0, 6, "Phone: 091-555-0142", ln=True)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 15)
    pdf.cell(0, 9, "INVOICE", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Invoice No: " + inv_no, ln=True)
    pdf.cell(0, 6, "Date: " + date, ln=True)
    pdf.cell(0, 6, "Due Date: " + due, ln=True)
    pdf.cell(0, 6, "Bill To: Spice House Restaurant", ln=True)
    pdf.ln(6)
    # header row
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(52, 8, "Item", border=1)
    pdf.cell(18, 8, "Qty", border=1)
    pdf.cell(22, 8, "Unit", border=1)
    pdf.cell(32, 8, "Unit Price", border=1)
    pdf.cell(32, 8, "Line Total", border=1, ln=True)
    pdf.set_font("Helvetica", "", 11)
    for (item, qty, unit, price, total) in lines:
        pdf.cell(52, 8, item, border=1)
        pdf.cell(18, 8, str(qty), border=1)
        pdf.cell(22, 8, unit, border=1)
        pdf.cell(32, 8, "$%.2f" % price, border=1)
        pdf.cell(32, 8, "$%.2f" % total, border=1, ln=True)
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, f"Subtotal: ${subtotal:.2f}", ln=True)
    pdf.cell(0, 6, f"Tax (5%): ${tax:.2f}", ln=True)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, f"Grand Total: ${grand:.2f}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(4)
    pdf.cell(0, 6, "Payment due within 7 days. Thank you for your business.", ln=True)
    path = os.path.join(OUT, fname)
    pdf.output(path)
    print("wrote", path)

os.makedirs(OUT, exist_ok=True)

make_pdf("test-a-clean.pdf", "INV-2501", "23 November 2026", "30 November 2026",
         [("Tomatoes", 40, "kg", 3.50, 140.00),
          ("Onions", 25, "kg", 1.20, 30.00),
          ("Basmati Rice", 20, "kg", 2.40, 48.00)],
         218.00, 10.90, 228.90)

make_pdf("test-b-overcharged.pdf", "INV-2502", "24 November 2026", "1 December 2026",
         [("Tomatoes", 60, "kg", 4.20, 252.00),
          ("Onions", 20, "kg", 1.20, 24.00),
          ("Potatoes", 30, "kg", 0.90, 27.00)],
         303.00, 15.15, 318.15)

make_pdf("test-c-math-error.pdf", "INV-2503", "24 November 2026", "1 December 2026",
         [("Chicken Breast", 10, "kg", 6.80, 86.00),
          ("Garlic", 5, "kg", 3.10, 15.50),
          ("Lemons", 10, "kg", 1.80, 18.00)],
         119.50, 5.98, 125.48)

make_pdf("test-d-no-rate.pdf", "INV-2504", "25 November 2026", "2 December 2026",
         [("Tomatoes", 30, "kg", 3.50, 105.00),
          ("Saffron", 0.5, "kg", 180.00, 90.00),
          ("Ginger", 8, "kg", 4.60, 36.80)],
         231.80, 11.59, 243.39)

make_pdf("test-e-duplicate.pdf", "INV-2505", "25 November 2026", "2 December 2026",
         [("Tomatoes", 25, "kg", 3.50, 87.50),
          ("Tomatoes", 25, "kg", 3.50, 87.50),
          ("Cooking Oil", 10, "litre", 4.10, 41.00)],
         216.00, 10.80, 226.80)
