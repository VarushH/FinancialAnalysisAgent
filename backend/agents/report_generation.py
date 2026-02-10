# backend/agents/report_generation.py
"""
Report generation agent.
Generates PDF reports combining all analysis results.
"""

import os
import asyncio
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from django.conf import settings

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry


def create_pdf_report(
    session_id: int,
    analysis: str,
    compliance: str,
    risk: str,
    pages_count: int,
    audit_report: dict = None,
    risk_report: dict = None,
    financial_extraction: dict = None
) -> str:
    """
    Create a professional PDF report with all analysis results.
    """
    print(f"      → Creating PDF report for session {session_id}...")
    
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f'report_{session_id}.pdf')
    
    c = canvas.Canvas(report_path, pagesize=letter)
    width, height = letter
    y = height - 50
    
    def new_page():
        nonlocal y
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(50, 30, "Financial Analysis Agent")
        c.drawRightString(width - 50, 30, f"Session {session_id}")
        c.showPage()
        y = height - 50
    
    def check_page(needed=100):
        nonlocal y
        # Ensure we never go below 60 (footer is at 30)
        if y < max(needed, 60):
            new_page()
        return y
    
    def draw_section_header(title):
        nonlocal y
        check_page(100)
        y -= 10
        c.setStrokeColor(colors.HexColor("#3498db"))
        c.setLineWidth(2)
        c.line(50, y, width - 50, y)
        y -= 25
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawString(50, y, title)
        c.setFillColor(colors.black)
        y -= 25
        c.setLineWidth(1)
    
    def draw_subsection(title):
        nonlocal y
        check_page(60)
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(colors.HexColor("#34495e"))
        c.drawString(60, y, title)
        c.setFillColor(colors.black)
        y -= 18
    
    # === TITLE PAGE ===
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.HexColor("#2c3e50"))
    c.drawCentredString(width/2, height - 150, "Financial Analysis Report")
    c.setFillColor(colors.black)
    
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height - 190, f"Session ID: {session_id}")
    c.drawCentredString(width/2, height - 210, f"Pages Analyzed: {pages_count}")
    
    # Summary scores on title page
    if audit_report or risk_report:
        y_scores = height - 280
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width/2, y_scores, "Executive Summary")
        y_scores -= 30
        
        if audit_report:
            score = audit_report.get('compliance_score', 0)
            color = colors.green if score >= 80 else colors.orange if score >= 60 else colors.red
            c.setFillColor(color)
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(width/2 - 80, y_scores, f"Compliance: {score}/100")
            c.setFillColor(colors.black)
        
        if risk_report:
            score = risk_report.get('risk_score', 0)
            level = risk_report.get('risk_level', 'N/A')
            color = colors.green if score < 30 else colors.orange if score < 60 else colors.red
            c.setFillColor(color)
            c.setFont("Helvetica-Bold", 12)
            c.drawCentredString(width/2 + 80, y_scores, f"Risk: {score}/100 ({level})")
            c.setFillColor(colors.black)
    
            c.drawCentredString(width/2 + 80, y_scores, f"Risk: {score}/100 ({level})")
            c.setFillColor(colors.black)
    
    new_page()

    # === FINANCE ANALYSIS ===
    draw_section_header("Finance Analysis")
    
    # Split Analysis and RAG Q&A if present
    rag_delimiter = "[RAG Q&A]"
    main_analysis = analysis
    rag_content = None
    
    
    if rag_delimiter in analysis:
        print(f"      ✅ Found RAG delimiter in analysis (len={len(analysis)})")
        parts = analysis.split(rag_delimiter)
        main_analysis = parts[0].strip()
        if len(parts) > 1:
            rag_content = parts[1].strip()
            print(f"      ✅ Extracted RAG content (len={len(rag_content)})")
        else:
            print("      ⚠️ RAG delimiter found but no content after it")
    else:
        print(f"      ⚠️ RAG delimiter '{rag_delimiter}' NOT found in analysis (len={len(analysis)})")
        # Fallback: check if it's just missing the exact delimiter string but has content
        if "Q:" in analysis and "A:" in analysis:
             print("      ⚠️ Potential RAG content found without delimiter, trying heuristics...")
    
    c.setFont("Helvetica", 10)
    for line in _wrap_text(main_analysis, 90):
        y = check_page(15)
        c.drawString(60, y, line)
        y -= 13
    y -= 15

    # === RAG Q&A SECTION ===
    if rag_content:
        draw_subsection("Q&A with Finance Agent")
        c.setFont("Helvetica", 10)
        # Handle newlines in RAG content for better readability
        for paragraph in rag_content.split('\n'):
            if not paragraph.strip():
                continue
            for line in _wrap_text(paragraph, 90):
                y = check_page(15)
                c.drawString(60, y, line)
                y -= 13
            y -= 5 # Extra space between paragraphs
        y -= 10
    
    # === COMPLIANCE CHECK ===
    draw_section_header("Compliance Check")
    c.setFont("Helvetica", 10)
    for line in _wrap_text(compliance, 90):
        y = check_page(15)
        c.drawString(60, y, line)
        y -= 13
    y -= 15
    
    # === RISK ASSESSMENT ===
    draw_section_header("Risk Assessment")
    c.setFont("Helvetica", 10)
    for line in _wrap_text(risk, 90):
        y = check_page(15)
        c.drawString(60, y, line)
        y -= 13
    y -= 15    

    # === DETAILED FINANCIAL EXTRACTION ===
    if financial_extraction:
        # Force start on a new page for Detailed Finance Analysis
        c.showPage()
        y = height - 50
        
        # Main Title for this page
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawCentredString(width/2, y, "Detailed Finance Analysis Report")
        c.setFillColor(colors.black)
        y -= 40
        
        # Financial Summary Section
        fs = financial_extraction.get('financial_summary', {})
        if fs:
            draw_section_header("Financial Performance Summary (FY2024)")
            
            # Create a visual box or structured list for key metrics
            metrics = [
                ("Total Revenue", fs.get('revenue_2024', 'N/A')),
                ("Net Income", fs.get('net_income_2024', 'N/A')),
                ("Total Assets", fs.get('total_assets', 'N/A')),
                ("Total Liabilities", fs.get('total_liabilities', 'N/A')),
                ("Total Equity", fs.get('total_equity', 'N/A')),
                ("Debt-to-Equity Ratio", fs.get('debt_to_equity', 'N/A'))
            ]
            
            # Draw metrics in a 2x2 grid if possible, or list
            # Let's do a clean list with distinct formatting
            c.setFont("Helvetica", 10)
            
            start_y = y
            for i, (name, val) in enumerate(metrics):
                # Check for page break (unlikely at top of new page but good practice)
                y = check_page(30)
                
                # Draw label
                c.setFont("Helvetica-Bold", 11)
                c.setFillColor(colors.HexColor("#34495e"))
                c.drawString(70, y, f"{name}:")
                
                # Draw value
                c.setFont("Helvetica", 11)
                c.setFillColor(colors.black)
                # Align value to the right of the label area
                c.drawString(220, y, str(val))
                
                y -= 25 # Spacing between rows
            
            y -= 10

        # extracted extraction numbers (Significant Ratios/Figures)
        numbers = financial_extraction.get('numbers', [])
        if numbers:
            draw_subsection("Key Extracted Figures & Ratios")
            for num in numbers:
                 y = check_page(15)
                 c.setFont("Helvetica", 10)
                 c.drawString(70, y, f"• {num}")
                 y -= 15
            y -= 10

        # Important Dates
        dates = financial_extraction.get('important_dates', [])
        if dates:
            draw_subsection(f"Significant Dates ({len(dates)})")
            
            # Header
            if y < 40: y = check_page(40)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(70, y, "Date")
            c.drawString(180, y, "Event / Context")
            y -= 5
            c.line(70, y, width-70, y)
            y -= 15
            
            for date_item in dates:
                y = check_page(20)
                d = date_item.get('date', 'N/A')
                s = date_item.get('significance', 'N/A')
                
                c.setFont("Helvetica-Bold", 9)
                c.drawString(70, y, d)
                c.setFont("Helvetica", 9)
                c.drawString(180, y, s)
                y -= 15
            y -= 10

        # Companies & Currencies
        companies = financial_extraction.get('companies', [])
        currencies = financial_extraction.get('currencies', [])
        
        if companies or currencies:
            draw_subsection("Entities & Currency")
            
            if companies:
                y = check_page(20)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(70, y, "Companies Mentioned:")
                y -= 15
                c.setFont("Helvetica", 10)
                comp_str = ", ".join(companies)
                for line in _wrap_text(comp_str, 80):
                    y = check_page(15)
                    c.drawString(85, y, line)
                    y -= 12
                y -= 10
                
            if currencies:
                y = check_page(20)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(70, y, "Reporting Currencies:")
                c.setFont("Helvetica", 10)
                c.drawString(200, y, ", ".join(currencies))
                y -= 20

        # End of Detailed Section, add a separator or just space
        y -= 20

    
    # === DETAILED COMPLIANCE AUDIT ===
    if audit_report:
        # Force new page and reset Y to safe starting position
        c.showPage()
        y = height - 80  # Start lower from top
        
        # Section Title
        c.setStrokeColor(colors.HexColor("#3498db"))
        c.setLineWidth(2)
        c.line(50, y + 10, width - 50, y + 10)
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawString(50, y - 20, "Detailed Compliance Audit")
        c.setFillColor(colors.black)
        c.setLineWidth(1)
        y -= 60
        
        # Compliance Score
        score = audit_report.get('compliance_score', 0)
        score_color = colors.green if score >= 80 else colors.orange if score >= 60 else colors.red
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, y, "Overall Compliance Score:")
        c.setFillColor(score_color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(250, y, f"{score}/100")
        c.setFillColor(colors.black)
        y -= 50
        
        # Regulatory Rules
        rules = audit_report.get('rules_check', [])
        if rules:
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(colors.HexColor("#34495e"))
            c.drawString(60, y, f"Regulatory Compliance Rules ({len(rules)})")
            c.setFillColor(colors.black)
            y -= 25
            
            for rule in rules:
                # Check if we need new page (need at least 150px for a rule)
                if y < 150:
                    c.setFont("Helvetica-Oblique", 8)
                    c.drawString(50, 30, "Financial Analysis Agent")
                    c.showPage()
                    y = height - 80
                
                rule_id = rule.get('rule_id', 'N/A')
                status = rule.get('status', 'Unknown')
                requirement = rule.get('requirement', '')
                evidence = rule.get('evidence', '')
                
                # Rule ID and Status
                status_color = colors.green if status == 'Compliant' else colors.red if status == 'Non-Compliant' else colors.orange
                c.setFont("Helvetica-Bold", 10)
                c.drawString(70, y, f"[{rule_id}]")
                c.setFillColor(status_color)
                c.drawString(180, y, status)
                c.setFillColor(colors.black)
                y -= 20
                
                # Requirement
                c.setFont("Helvetica", 9)
                for line in _wrap_text(requirement, 80):
                    if y < 80:
                        c.showPage()
                        y = height - 80
                    c.drawString(80, y, line)
                    y -= 14
                
                # Evidence
                if evidence:
                    y -= 8
                    c.setFont("Helvetica-Oblique", 8)
                    c.setFillColor(colors.HexColor("#555555"))
                    for line in _wrap_text(f"Evidence: {evidence}", 85):
                        if y < 80:
                            c.showPage()
                            y = height - 80
                        c.drawString(80, y, line)
                        y -= 13
                    c.setFillColor(colors.black)
                
                y -= 25  # Space between rules
        
        # Risk Flags
        flags = audit_report.get('risk_flags', [])
        if flags:
            y -= 15  # Increased from 10
            draw_subsection(f"Identified Risk Flags ({len(flags)})")
            for flag in flags:
                y = check_page(55)  # Increased from 35
                severity = flag.get('severity', 'Unknown')
                risk_type = flag.get('risk_type', 'N/A')
                description = flag.get('description', '')
                
                sev_color = colors.red if severity == 'High' else colors.orange if severity == 'Medium' else colors.green
                c.setFillColor(sev_color)
                c.setFont("Helvetica-Bold", 10)
                c.drawString(70, y, f"● {severity.upper()}")
                c.setFillColor(colors.black)
                c.setFont("Helvetica", 10)
                c.drawString(140, y, f"- {risk_type}")
                y -= 16  # Increased from 14
                
                c.setFont("Helvetica", 9)
                for line in _wrap_text(description, 80)[:2]:
                    c.drawString(85, y, line)
                    y -= 13  # Increased from 11
                y -= 10  # Increased from 6
        
        # Recommendations
        annotations = audit_report.get('annotations', [])
        if annotations:
            y -= 10
            draw_subsection("Recommendations")
            for i, annotation in enumerate(annotations[:5], 1):
                y = check_page(25)
                c.setFont("Helvetica", 9)
                lines = _wrap_text(f"{i}. {annotation}", 85)
                for line in lines[:2]:
                    c.drawString(70, y, line)
                    y -= 11
                y -= 5
    
    # === DETAILED RISK ASSESSMENT ===
    if risk_report:
        # Start on a new page
        c.showPage()
        y = height - 80
        
        # Section Title
        c.setStrokeColor(colors.HexColor("#3498db"))
        c.setLineWidth(2)
        c.line(50, y + 10, width - 50, y + 10)
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#2c3e50"))
        c.drawString(50, y - 20, "Detailed Risk Assessment")
        c.setFillColor(colors.black)
        c.setLineWidth(1)
        y -= 60
        
        # Risk Score
        score = risk_report.get('risk_score', 0)
        level = risk_report.get('risk_level', 'N/A')
        score_color = colors.green if score < 30 else colors.orange if score < 60 else colors.red
        
        c.setFont("Helvetica-Bold", 13)
        c.drawString(60, y, "Risk Score:")
        c.setFillColor(score_color)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(150, y, f"{score}/100 ({level})")
        c.setFillColor(colors.black)
        y -= 50
        
        # Financial Ratios
        ratios = risk_report.get('ratios', [])
        if ratios:
            draw_subsection("Financial Ratios")
            
            # Table header
            c.setFont("Helvetica-Bold", 9)
            c.drawString(70, y, "Ratio Name")
            c.drawString(200, y, "Value")
            c.drawString(280, y, "Benchmark")
            c.drawString(380, y, "Status")
            y -= 5
            c.line(70, y, 450, y)
            y -= 12
            
            for ratio in ratios:
                y = check_page(18)
                name = ratio.get('name', 'N/A')
                value = ratio.get('value')
                value_str = f"{value:.2f}" if value is not None else "N/A"
                benchmark = ratio.get('benchmark', 'N/A')
                status = ratio.get('status', 'N/A')
                
                status_color = colors.green if status == 'Good' else colors.red if status == 'Poor' else colors.orange
                
                c.setFont("Helvetica", 9)
                c.drawString(70, y, name[:20])
                c.drawString(200, y, value_str)
                c.drawString(280, y, str(benchmark))
                c.setFillColor(status_color)
                c.drawString(380, y, status)
                c.setFillColor(colors.black)
                y -= 14
            y -= 10
        
        # Anomalies
        anomalies = risk_report.get('anomalies', [])
        if anomalies:
            draw_subsection(f"Detected Anomalies ({len(anomalies)})")
            for anomaly in anomalies:
                y = check_page(20)
                item = anomaly.get('item', 'N/A')
                change = anomaly.get('yoy_change', 0)
                severity = anomaly.get('severity', 'Medium')
                
                sev_color = colors.red if severity == 'High' else colors.orange
                c.setFillColor(sev_color)
                c.setFont("Helvetica-Bold", 9)
                c.drawString(70, y, "●")
                c.setFillColor(colors.black)
                c.setFont("Helvetica", 9)
                c.drawString(85, y, f"{item}: {change:+.1f}% YoY change")
                y -= 14
            y -= 10
        
        # Key Insights
        insights = risk_report.get('key_insights', [])
        if insights:
            draw_subsection("Key Insights")
            for insight in insights[:6]:
                y = check_page(25)
                c.setFont("Helvetica", 9)
                lines = _wrap_text(f"• {insight}", 85)
                for line in lines[:2]:
                    c.drawString(70, y, line)
                    y -= 11
                y -= 4
    
    # Final footer
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 30, "Generated by Financial Analysis Agent")
    c.drawRightString(width - 50, 30, f"Session {session_id}")
    
    c.showPage()
    c.save()
    
    print(f"      ✅ PDF saved successfully")
    return report_path


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap text to fit within max characters per line."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 <= max_chars:
            current_line.append(word)
            current_length += len(word) + 1
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return lines if lines else [text]


@agent_retry(agent_name="report_generation")
async def process_async(state: AgentState) -> AgentState:
    """
    Async process function for report generation.
    """
    print("\n   📝 REPORT GENERATION AGENT")
    print("   " + "-"*40)
    
    state = add_message(state, "report_generation", "Report generation started")
    state["current_agent"] = "report_generation"
    
    session_id = state.get("session_id", 0)
    analysis = state.get("analysis_result", "No analysis available")
    compliance = state.get("compliance_result", "No compliance check available")
    risk = state.get("risk_result", "No risk assessment available")
    pages = state.get("pages", [])
    
    print(f"      Session: {session_id}")
    print(f"      Pages: {len(pages)}")
    print(f"      Analysis: {analysis[:40]}...")
    print(f"      Compliance: {compliance[:40]}...")
    print(f"      Risk: {risk[:40]}...")
    
    # Get detailed reports
    audit_report = state.get("audit_report")
    risk_report = state.get("risk_report")
    print(f"      Audit report: {'Yes' if audit_report else 'No'}")
    print(f"      Risk report: {'Yes' if risk_report else 'No'}")
    
    # Run PDF generation in thread pool
    loop = asyncio.get_event_loop()
    from functools import partial
    pdf_func = partial(
        create_pdf_report,
        session_id,
        analysis,
        compliance,
        risk,
        len(pages),
        audit_report,
        risk_report,
        state.get("financial_extraction")
    )
    report_path = await loop.run_in_executor(None, pdf_func)
    
    state["report_path"] = report_path
    state["status"] = "completed"
    
    print(f"   ✅ Report generated: {report_path}")
    
    # Save report_path to database so download works
    from api.models import AnalysisSession
    AnalysisSession.objects.filter(pk=session_id).update(report_file=report_path)
    print(f"   💾 Report saved to database")
    
    state = add_message(state, "report_generation", "Report generation completed")
    return state


# Legacy sync process function
def process(session, analysis, compliance, risk, send_message):
    """Legacy synchronous process function."""
    send_message("Report generation started")
    
    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f'report_{session.id}.pdf')
    
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
