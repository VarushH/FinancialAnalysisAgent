# Generates a PDF report using ReportLab, combining all analysis results. The PDF is saved to the media/reports/ directory, and the session’s report_file path is updated.

# backend/agents/report_generation.py
import os
from reportlab.pdfgen import canvas
from django.conf import settings

def process(session, analysis, compliance, risk, send_message):
    send_message("Report generation started")
    # Ensure reports directory exists
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f'report_{session.id}.pdf')

    # Create PDF
    c = canvas.Canvas(report_path)
    c.setFont("Helvetica", 14)
    c.drawString(100, 800, f"Financial Analysis Report - Session {session.id}")
    c.setFont("Helvetica", 12)
    c.drawString(100, 760, f"Finance Analysis: {analysis}")
    c.drawString(100, 740, f"Compliance Check: {compliance}")
    c.drawString(100, 720, f"Risk Assessment: {risk}")
    c.showPage()
    c.save()

    session.report_file = report_path
    session.status = 'completed'
    session.save()
    send_message("Report generation completed")
