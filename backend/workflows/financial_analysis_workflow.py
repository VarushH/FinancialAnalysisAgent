
# backend/workflows/financial_analysis_workflow.py
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from api.models import AnalysisSession
from agents.document_extraction import process as doc_extract
from agents.finance_analysis import process as finance_analyze
from agents.compliance import process as compliance_check
from agents.risk_assessment import process as risk_assess
from agents.report_generation import process as generate_report

def run_analysis_pipeline(session_id):
    session = AnalysisSession.objects.get(pk=session_id)
    channel_layer = get_channel_layer()
    group_name = f'analysis_{session_id}'

    def send(message):
        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "progress_message", "message": message}
        )

    # Document Extraction
    pages, tables = doc_extract(session, send)

    # Finance Analysis
    analysis_result = finance_analyze(pages, tables, send)

    # Compliance Checking
    compliance_result = compliance_check(pages, send)

    # Risk Assessment
    risk_result = risk_assess(pages, compliance_result, send)

    # Report Generation
    generate_report(session, analysis_result, compliance_result, risk_result, send)
