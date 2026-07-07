# backend/agents/report_generation.py
"""
Report generation agent.
Generates professional PDF reports using ReportLab Platypus (flowable layout):
real tables, automatic wrapping, automatic page breaks, and a running footer.

This version adds, per agent: a methodology line, explicit per-item status
breakdowns (which items are compliant / observation / non-compliant, which
ratios are healthy vs concerning, anomalies by severity), and fuller sections.
"""

import os
import math
import asyncio
from functools import partial

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether,
)

from django.conf import settings

from workflows.state import AgentState, add_message, set_error
from workflows.retry import agent_retry
from agents.finance_analysis import _parse_financial_value


# --- Palette ---
NAVY  = colors.HexColor("#1F2D3D")
SLATE = colors.HexColor("#34495E")
BLUE  = colors.HexColor("#2E86DE")
GREY  = colors.HexColor("#6B7280")
ZEBRA = colors.HexColor("#F7F9FC")
GREEN = colors.HexColor("#1E9E62")
AMBER = colors.HexColor("#E08A1E")
RED   = colors.HexColor("#D64541")
LINE  = colors.HexColor("#D9E0E7")


def _styles():
    ss = getSampleStyleSheet()
    return {
        "title":    ParagraphStyle("title", parent=ss["Title"], fontName="Helvetica-Bold",
                                   fontSize=26, textColor=NAVY, spaceAfter=6, alignment=TA_CENTER),
        "subtitle": ParagraphStyle("subtitle", parent=ss["Normal"], fontSize=12,
                                   textColor=GREY, alignment=TA_CENTER, spaceAfter=2),
        "h1":       ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold",
                                   fontSize=15, textColor=NAVY, spaceBefore=6, spaceAfter=8),
        "h2":       ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold",
                                   fontSize=11.5, textColor=SLATE, spaceBefore=10, spaceAfter=5),
        "body":     ParagraphStyle("body", parent=ss["Normal"], fontSize=9.5,
                                   textColor=colors.HexColor("#222B36"), leading=14, spaceAfter=4),
        "method":   ParagraphStyle("method", parent=ss["Normal"], fontSize=8.5,
                                   textColor=GREY, leading=12, spaceAfter=6, italic=True,
                                   fontName="Helvetica-Oblique"),
        "small":    ParagraphStyle("small", parent=ss["Normal"], fontSize=8.5,
                                   textColor=GREY, leading=12),
        "cell":     ParagraphStyle("cell", parent=ss["Normal"], fontSize=9, leading=12),
        "cellb":    ParagraphStyle("cellb", parent=ss["Normal"], fontSize=9, leading=12,
                                   fontName="Helvetica-Bold", textColor=SLATE),
        "kpi_lbl":  ParagraphStyle("kpi_lbl", parent=ss["Normal"], fontSize=9,
                                   textColor=colors.white, alignment=TA_CENTER, leading=12),
        "kpi_val":  ParagraphStyle("kpi_val", parent=ss["Normal"], fontName="Helvetica-Bold",
                                   fontSize=22, leading=26, textColor=colors.white,
                                   alignment=TA_CENTER),
        "kpi_status": ParagraphStyle("kpi_status", parent=ss["Normal"], fontName="Helvetica-Bold",
                                     fontSize=11, leading=14, textColor=colors.white,
                                     alignment=TA_CENTER),
    }


def _section(title, styles):
    return KeepTogether([
        HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=4, spaceAfter=6),
        Paragraph(title, styles["h1"]),
    ])


def _method(text, styles):
    """Italic grey 'how this was determined' line."""
    return Paragraph(f"<b>How this was determined:</b> {text}", styles["method"])


def _chip(text, color):
    return f'<font color="{color.hexval()}"><b>{text}</b></font>'


def _status_color(status):
    return GREEN if status == "Compliant" else RED if status == "Non-Compliant" else AMBER


def _sev_color(sev):
    return RED if sev == "High" else AMBER if sev == "Medium" else GREEN


def _table(rows, col_widths, header_bg=NAVY):
    t = Table(rows, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), header_bg),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


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
    """Create a professional, flowable-based PDF report with detailed per-agent sections."""
    print(f"      → Creating PDF report for session {session_id}...")

    report_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f'report_{session_id}.pdf')

    styles = _styles()
    width, height = letter

    def _decorate(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(50, 42, width - 50, 42)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)
        canvas.drawString(50, 30, "Generated by Financial Analysis Agent")
        canvas.drawCentredString(width / 2, 30, f"Session {session_id}")
        canvas.drawRightString(width - 50, 30, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        report_path, pagesize=letter,
        leftMargin=54, rightMargin=54, topMargin=58, bottomMargin=54,
        title=f"Financial Analysis Report - Session {session_id}",
    )
    content_w = doc.width
    story = []

    # ===================================================== TITLE + KPI band
    story.append(Spacer(1, 90))
    story.append(Paragraph("Financial Analysis Report", styles["title"]))
    story.append(Paragraph("Automated Multi-Agent Analysis", styles["subtitle"]))
    story.append(HRFlowable(width="40%", thickness=1, color=LINE,
                            spaceBefore=8, spaceAfter=18, hAlign="CENTER"))
    meta = Table(
        [[Paragraph("Session ID", styles["small"]), Paragraph(str(session_id), styles["cellb"])],
         [Paragraph("Pages Analyzed", styles["small"]), Paragraph(str(pages_count), styles["cellb"])]],
        colWidths=[110, 110], hAlign="CENTER",
    )
    meta.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
                              ("TOPPADDING", (0, 0), (-1, -1), 4),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.append(meta)
    story.append(Spacer(1, 34))

    if audit_report or risk_report:
        story.append(Paragraph("Executive Summary", styles["h2"]))
        cells = []
        if audit_report:
            cs = audit_report.get('compliance_score', 0)
            cells.append(("COMPLIANCE", f"{cs}/100", audit_report.get('overall_status', ''),
                          GREEN if cs >= 80 else AMBER if cs >= 60 else RED))
        if risk_report:
            overall = risk_report.get('overall_risk') or risk_report.get('risk_level', 'N/A')
            rs = risk_report.get('risk_score')
            rs_txt = f"{rs}/100" if rs is not None else "n/a"
            cells.append(("RISK", rs_txt, overall,
                          GREEN if overall == "LOW" else AMBER if overall == "MEDIUM" else RED))
        inner = []
        for lbl, score, status, col in cells:
            # Three stacked paragraphs (label / score / status) so lines can never overlap.
            block = Table(
                [[Paragraph(lbl, styles["kpi_lbl"])],
                 [Paragraph(score, styles["kpi_val"])],
                 [Paragraph(status, styles["kpi_status"])]],
                colWidths=[content_w / len(cells) - 12],
            )
            block.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), col),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (0, 0), 16),   # breathing room above label
                ("BOTTOMPADDING", (0, 0), (0, 0), 4),
                ("TOPPADDING", (0, 1), (0, 1), 0),    # score
                ("BOTTOMPADDING", (0, 1), (0, 1), 4),
                ("TOPPADDING", (0, 2), (0, 2), 0),    # status
                ("BOTTOMPADDING", (0, 2), (0, 2), 16),
            ]))
            inner.append(block)
        band = Table([inner], colWidths=[content_w / len(inner)] * len(inner))
        band.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 6),
                                  ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                  ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        story.append(band)

    story.append(PageBreak())

    # ===================================================== SUMMARIES (page 2)
    story.append(_section("Finance Analysis", styles))
    story.append(_method("LLM extraction of financial statements; YoY and margins computed in code "
                         "from the parsed period values.", styles))
    main_analysis, rag_content = analysis, None
    if "[RAG Q&A]" in analysis:
        parts = analysis.split("[RAG Q&A]")
        main_analysis = parts[0].strip()
        if len(parts) > 1:
            rag_content = parts[1].strip()
    for para in [p for p in main_analysis.split("\n") if p.strip()]:
        story.append(Paragraph(para.strip(), styles["body"]))
    if rag_content:
        story.append(Paragraph("Q&amp;A with Finance Agent", styles["h2"]))
        for para in [p for p in rag_content.split("\n") if p.strip()]:
            story.append(Paragraph(para.strip().replace("&", "&amp;"), styles["body"]))

    story.append(_section("Compliance Check", styles))
    story.append(_method("5-check rubric \u2014 3 checks judged by the LLM from document text, "
                         "2 computed from financial ratios; score is the sum of check results.", styles))
    for para in [p for p in compliance.split("\n") if p.strip()]:
        story.append(Paragraph(para.strip(), styles["body"]))

    story.append(_section("Risk Assessment", styles))
    story.append(_method("Two independent signals \u2014 a keyword scan of the text and a financial "
                         "ratio/anomaly engine \u2014 reconciled into one verdict (the more severe of the two).",
                         styles))
    for para in [p for p in risk.split("\n") if p.strip()]:
        story.append(Paragraph(para.strip(), styles["body"]))

    # ===================================================== DETAILED FINANCE
    fs = (financial_extraction or {}).get('financial_summary', {})
    periods = fs.get('periods', []) if isinstance(fs, dict) else []
    if financial_extraction:
        story.append(PageBreak())
        story.append(_section("Detailed Finance Analysis", styles))
        story.append(_method("Metrics extracted per fiscal period by the LLM; YoY % and Net Margin "
                             "computed from the parsed values.", styles))

        if periods:
            story.append(Paragraph("Financial Performance Summary", styles["h2"]))
            disp = periods[:3]

            def yoy(key):
                if len(disp) < 2:
                    return "\u2014"
                n = _parse_financial_value(disp[0].get(key))
                o = _parse_financial_value(disp[1].get(key))
                if not math.isnan(n) and not math.isnan(o) and o != 0:
                    return f"{(n - o) / abs(o):+.1%}"
                return "\u2014"

            header = ["Metric"] + [str(p.get("period", "N/A")) for p in disp]
            if len(disp) >= 2:
                header.append("YoY %")
            rows = [[Paragraph(h, styles["cellb"]) for h in header]]
            for label, key in [("Total Revenue", "revenue"), ("Net Income", "net_income"),
                               ("Total Assets", "total_assets"), ("Total Liabilities", "total_liabilities"),
                               ("Total Equity", "total_equity"), ("Debt-to-Equity", "debt_to_equity")]:
                row = [Paragraph(label, styles["cellb"])]
                row += [Paragraph(str(p.get(key, "N/A")), styles["cell"]) for p in disp]
                if len(disp) >= 2:
                    row.append(Paragraph(yoy(key), styles["cell"]))
                rows.append(row)
            margin_row = [Paragraph("Net Margin", styles["cellb"])]
            for p in disp:
                rev = _parse_financial_value(p.get("revenue"))
                ni = _parse_financial_value(p.get("net_income"))
                margin_row.append(Paragraph(
                    f"{ni / rev:.1%}" if (not math.isnan(rev) and rev != 0 and not math.isnan(ni)) else "N/A",
                    styles["cell"]))
            if len(disp) >= 2:
                margin_row.append(Paragraph("\u2014", styles["cell"]))
            rows.append(margin_row)

            ncols = len(header)
            first = content_w * 0.30
            rest = (content_w - first) / (ncols - 1)
            t = _table(rows, [first] + [rest] * (ncols - 1))
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
                ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(t)
            story.append(Spacer(1, 10))

        numbers = financial_extraction.get('numbers', [])
        if numbers:
            story.append(Paragraph("Key Extracted Figures &amp; Ratios", styles["h2"]))
            for n in numbers:
                story.append(Paragraph(f"• {n}", styles["body"]))

        dates = financial_extraction.get('important_dates', [])
        if dates:
            story.append(Paragraph(f"Significant Dates ({len(dates)})", styles["h2"]))
            rows = [[Paragraph("Date", styles["cellb"]), Paragraph("Event / Context", styles["cellb"])]]
            for d in dates:
                rows.append([Paragraph(str(d.get('date', 'N/A')), styles["cell"]),
                             Paragraph(str(d.get('significance', 'N/A')), styles["cell"])])
            story.append(_table(rows, [content_w * 0.28, content_w * 0.72], header_bg=SLATE))
            story.append(Spacer(1, 8))

        companies = financial_extraction.get('companies', [])
        currencies = financial_extraction.get('currencies', [])
        if companies or currencies:
            story.append(Paragraph("Entities &amp; Currency", styles["h2"]))
            if companies:
                story.append(Paragraph(f"<b>Companies:</b> {', '.join(companies)}", styles["body"]))
            if currencies:
                story.append(Paragraph(f"<b>Reporting Currencies:</b> {', '.join(currencies)}", styles["body"]))

    # ===================================================== DETAILED COMPLIANCE
    if audit_report:
        story.append(PageBreak())
        story.append(_section("Detailed Compliance Audit", styles))
        story.append(_method("Each of the 5 checks is graded Compliant / Observation / Non-Compliant. "
                             "Checks C1\u2013C3 are LLM judgments from the text; C4\u2013C5 are computed from "
                             "the financial ratios (same engine as the Risk section).", styles))

        cs = audit_report.get('compliance_score', 0)
        overall = audit_report.get('overall_status', 'N/A')
        c_col = GREEN if cs >= 80 else AMBER if cs >= 60 else RED
        story.append(Paragraph(
            f'Overall: {_chip(overall, c_col)} &nbsp;|&nbsp; Score {_chip(f"{cs}/100", c_col)}', styles["body"]))

        rules = audit_report.get('rules_check', [])
        if rules:
            # --- Per-status breakdown (which checks fall into each bucket) ---
            by_status = {"Compliant": [], "Observation": [], "Non-Compliant": []}
            for r in rules:
                by_status.setdefault(r.get('status', 'Observation'), []).append(
                    f"{r.get('rule_id', '')} {r.get('name', '')}".strip())
            story.append(Paragraph("Breakdown by status", styles["h2"]))
            for status_name, col in [("Compliant", GREEN), ("Observation", AMBER), ("Non-Compliant", RED)]:
                items = by_status.get(status_name, [])
                listing = ", ".join(items) if items else "none"
                story.append(Paragraph(f'{_chip(status_name, col)} ({len(items)}): {listing}', styles["body"]))
            story.append(Spacer(1, 6))

            # --- Full checks table ---
            story.append(Paragraph(f"Compliance Checks Verified ({len(rules)})", styles["h2"]))
            rows = [[Paragraph(h, styles["cellb"]) for h in ("Check", "Status", "Evidence")]]
            for r in rules:
                status = r.get('status', 'Unknown')
                name_cell = f'<b>{r.get("rule_id", "")}</b> &nbsp;{r.get("name") or r.get("requirement", "")}'
                rows.append([
                    Paragraph(name_cell, styles["cell"]),
                    Paragraph(_chip(status, _status_color(status)), styles["cell"]),
                    Paragraph(r.get('evidence', '') or "\u2014", styles["cell"]),
                ])
            story.append(_table(rows, [content_w * 0.34, content_w * 0.16, content_w * 0.50]))
            story.append(Spacer(1, 8))

        flags = audit_report.get('risk_flags', [])
        if flags:
            story.append(Paragraph(f"Risk Flags ({len(flags)})", styles["h2"]))
            for f in flags:
                sev = f.get('severity', 'Unknown')
                story.append(Paragraph(
                    f'{_chip(sev.upper(), _sev_color(sev))} &nbsp;<b>{f.get("risk_type", "N/A")}</b> — '
                    f'{f.get("description", "")}', styles["body"]))
            story.append(Spacer(1, 4))

        trail = audit_report.get('audit_trail', '')
        if trail:
            story.append(Paragraph("Audit Trail", styles["h2"]))
            for ln in [x.strip() for x in str(trail).replace(';', '\n').split('\n') if x.strip()]:
                story.append(Paragraph(f"• {ln}", styles["small"]))
            story.append(Spacer(1, 6))

        annotations = audit_report.get('annotations', [])
        if annotations:
            story.append(Paragraph("Recommendations", styles["h2"]))
            for i, a in enumerate(annotations[:5], 1):
                story.append(Paragraph(f"{i}. {a}", styles["body"]))

    # ===================================================== DETAILED RISK
    if risk_report:
        story.append(PageBreak())
        story.append(_section("Detailed Risk Assessment", styles))
        story.append(_method("Verdict reconciles a keyword scan of the text with a financial ratio/anomaly "
                             "engine, taking the more severe of the two signals.", styles))

        overall = risk_report.get('overall_risk') or risk_report.get('risk_level', 'N/A')
        rs = risk_report.get('risk_score')
        o_col = GREEN if overall == "LOW" else AMBER if overall == "MEDIUM" else RED
        rs_txt = f"{rs}/100" if rs is not None else "n/a (no financial tables)"
        story.append(Paragraph(f'Overall Risk: {_chip(overall, o_col)} &nbsp;|&nbsp; Financial Score {rs_txt}',
                               styles["body"]))
        if risk_report.get('reconciliation'):
            story.append(Paragraph(risk_report['reconciliation'], styles["small"]))
        story.append(Spacer(1, 6))

        # --- Keyword analysis breakdown (which terms drove the keyword signal) ---
        ka = risk_report.get('keyword_analysis')
        if ka:
            story.append(Paragraph("Keyword Signal Breakdown", styles["h2"]))
            for lbl, key, col in [("High-risk terms", "high_terms", RED),
                                  ("Medium-risk terms", "medium_terms", AMBER),
                                  ("Positive terms", "positive_terms", GREEN)]:
                terms = ka.get(key, [])
                story.append(Paragraph(
                    f'{_chip(lbl, col)} ({len(terms)}): {", ".join(terms) if terms else "none"}', styles["body"]))
            story.append(Spacer(1, 6))

        # --- Ratios, grouped by health, then full table ---
        ratios = risk_report.get('ratios', [])
        if ratios:
            def _healthy(r):
                v, name = r.get('value'), (r.get('name') or '').lower()
                if v is None:
                    return None
                if 'current ratio' in name:
                    return v >= 1.0
                if 'debt to equity' in name:
                    return v <= 2.0
                if 'margin' in name:
                    return v >= 0
                return None
            healthy = [r for r in ratios if _healthy(r) is True]
            concern = [r for r in ratios if _healthy(r) is False]
            story.append(Paragraph("Ratio Health Breakdown", styles["h2"]))
            story.append(Paragraph(
                f'{_chip("Healthy", GREEN)} ({len(healthy)}): '
                f'{", ".join(f"{r.get("name")} {r.get("period")}" for r in healthy) or "none"}', styles["body"]))
            story.append(Paragraph(
                f'{_chip("Concerning", RED)} ({len(concern)}): '
                f'{", ".join(f"{r.get("name")} {r.get("period")}" for r in concern) or "none"}', styles["body"]))
            story.append(Spacer(1, 6))

            story.append(Paragraph("Financial Ratios", styles["h2"]))
            rows = [[Paragraph(h, styles["cellb"]) for h in ("Ratio", "Period", "Value", "Meaning")]]
            for r in ratios:
                val = r.get('value')
                val_str = f"{val:.2f}" if isinstance(val, (int, float)) else "N/A"
                rows.append([Paragraph(str(r.get('name', 'N/A')), styles["cell"]),
                             Paragraph(str(r.get('period', 'N/A')), styles["cell"]),
                             Paragraph(val_str, styles["cell"]),
                             Paragraph(str(r.get('description', '')), styles["small"])])
            story.append(_table(rows, [content_w * 0.20, content_w * 0.12, content_w * 0.12, content_w * 0.56]))
            story.append(Spacer(1, 8))

        # --- Anomalies, grouped by severity, then listed ---
        anomalies = risk_report.get('anomalies', [])
        if anomalies:
            by_sev = {"High": [], "Medium": [], "Low": []}
            for a in anomalies:
                by_sev.setdefault(a.get('severity', 'Low'), []).append(a)
            story.append(Paragraph(f"Detected Anomalies ({len(anomalies)})", styles["h2"]))
            for sev, col in [("High", RED), ("Medium", AMBER), ("Low", GREEN)]:
                grp = by_sev.get(sev, [])
                if not grp:
                    continue
                story.append(Paragraph(f'{_chip(sev + " severity", col)} ({len(grp)}):', styles["body"]))
                for a in grp:
                    change = a.get('yoy_change', 0)
                    pf, pt = a.get('period_from', ''), a.get('period_to', '')
                    pair = f" ({pf}\u2192{pt})" if pf else ""
                    change_txt = f"{change:+.1%}" if isinstance(change, (int, float)) else str(change)
                    story.append(Paragraph(f'&nbsp;&nbsp;• <b>{a.get("item", "N/A")}</b>: {change_txt}{pair}',
                                           styles["small"]))
            story.append(Spacer(1, 6))

        insights = risk_report.get('key_insights', [])
        if insights:
            story.append(Paragraph("Key Insights", styles["h2"]))
            for ins in insights[:6]:
                story.append(Paragraph(f"• {ins}", styles["body"]))

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    print(f"      ✅ PDF saved successfully")
    return report_path


@agent_retry(agent_name="report_generation")
async def process_async(state: AgentState) -> AgentState:
    """Aggregate agent results and render the detailed PDF report."""
    print("\n   📝 REPORT GENERATION AGENT")
    print("   " + "-" * 40)
    state = add_message(state, "report_generation", "Report generation started")
    state["current_agent"] = "report_generation"

    session_id = state.get("session_id", 0)
    analysis = state.get("analysis_result", "No analysis available")
    compliance = state.get("compliance_result", "No compliance check available")
    risk = state.get("risk_result", "No risk assessment available")
    pages = state.get("pages", [])

    audit_report = state.get("audit_report")
    risk_report = state.get("risk_report")
    print(f"      Audit report: {'Yes' if audit_report else 'No'} | Risk report: {'Yes' if risk_report else 'No'}")

    loop = asyncio.get_event_loop()
    pdf_func = partial(create_pdf_report, session_id, analysis, compliance, risk, len(pages),
                       audit_report, risk_report, state.get("financial_extraction"))
    report_path = await loop.run_in_executor(None, pdf_func)

    state["report_path"] = report_path
    state["status"] = "completed"
    print(f"   ✅ Report generated: {report_path}")

    from api.models import AnalysisSession

    def update_report_file(sid, path):
        AnalysisSession.objects.filter(pk=sid).update(report_file=path)

    await loop.run_in_executor(None, update_report_file, session_id, report_path)
    state = add_message(state, "report_generation", "Report generation completed")
    return state

