# backend/api/views.py
"""
API views for the financial analysis workflow.
Provides endpoints for upload, analysis control, and report download.
"""

import asyncio
import threading
import logging
import traceback
from django.shortcuts import get_object_or_404
from django.http import FileResponse, JsonResponse
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from .models import AnalysisSession
from .serializers import AnalysisSessionSerializer
from workflows.financial_analysis_workflow import (
    run_analysis_pipeline,
    resume_analysis_pipeline,
    get_workflow_state,
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
def upload_file(request):
    """
    Accepts a PDF file upload and creates an AnalysisSession.
    
    Returns:
        JSON with session_id
    """
    parser_classes = (MultiPartParser,)
    file_obj = request.FILES.get('file')
    
    if not file_obj:
        return Response({'error': 'No file provided'}, status=400)
    
    # Validate file type
    if not file_obj.name.lower().endswith('.pdf'):
        return Response({'error': 'Only PDF files are supported'}, status=400)
    
    session = AnalysisSession.objects.create(file=file_obj)
    return Response({
        'session_id': session.id,
        'status': session.status,
        'message': 'File uploaded successfully'
    })


@api_view(['POST'])
def start_analysis(request, session_id):
    """
    Starts the analysis pipeline in a background thread.
    Uses the new supervisor agent workflow with checkpoints.
    
    Returns:
        JSON with status and session_id
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    
    if session.status not in ['uploaded', 'failed']:
        return Response({
            'error': 'Analysis already started or completed',
            'current_status': session.status
        }, status=400)
    
    session.mark_processing()
    
    # Get optional user query
    user_query = request.data.get('query')
    
    # Run pipeline in background thread
    def run_pipeline():
        try:
            print(f"\n🔧 Running pipeline for session {session_id}...")
            final_state = run_analysis_pipeline(session_id, user_query)
            
            print(f"   Final state status: {final_state.get('status')}")
            print(f"   Requires approval: {final_state.get('requires_human_approval')}")
            print(f"   Approval checkpoint: {final_state.get('approval_checkpoint')}")
            
            # Update session based on final state
            session.refresh_from_db()
            
            if final_state.get('status') == 'completed':
                session.mark_completed(final_state.get('report_path'))
                print(f"   ✅ Session marked as completed")
            elif final_state.get('requires_human_approval'):
                # Workflow hit a human checkpoint
                checkpoint = final_state.get('approval_checkpoint', 'unknown')
                session.mark_awaiting_approval(checkpoint)
                print(f"   ⏸️ Session marked as awaiting approval at: {checkpoint}")
            elif final_state.get('error'):
                session.mark_failed(final_state.get('error'))
                print(f"   ❌ Session marked as failed")
            else:
                # Workflow paused at interrupt_before checkpoint
                # Check if current_agent indicates a checkpoint
                current = final_state.get('current_agent', '')
                if current in ['extraction_review', 'report_approval']:
                    session.mark_awaiting_approval(current)
                    print(f"   ⏸️ Session at checkpoint: {current}")
                else:
                    print(f"   ⚠️ Workflow ended with status: {final_state.get('status')}")
                    
        except Exception as e:
            logger.error(f"Pipeline failed for session {session_id}: {e}")
            print(f"   ❌ Pipeline exception: {e}")
            session.refresh_from_db()
            session.mark_failed(str(e))
    
    thread = threading.Thread(target=run_pipeline)
    thread.start()
    
    return Response({
        'status': 'processing',
        'session_id': session_id,
        'message': 'Analysis pipeline started'
    })


@api_view(['POST'])
def approve_checkpoint(request, session_id):
    """
    Approves a human-in-the-loop checkpoint and resumes the workflow.
    
    Body:
        feedback (optional): Human feedback or notes
        
    Returns:
        JSON with status
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    
    if not session.requires_approval:
        return Response({
            'error': 'No pending approval for this session',
            'current_status': session.status
        }, status=400)
    
    feedback = request.data.get('feedback', '')
    edited_content = request.data.get('edited_content', None)  # Get edited report content
    checkpoint = session.approval_checkpoint
    print(f"\n✅ Approving checkpoint: {checkpoint} for session {session_id}")
    if edited_content:
        print(f"   📝 Received edited content")
    
    session.approve_checkpoint()
    
    # Resume pipeline in background thread
    def resume_pipeline():
        try:
            # Pass the checkpoint name and edited content to resume from the correct phase
            final_state = resume_analysis_pipeline(session_id, feedback, checkpoint, edited_content)
            
            print(f"   Resume result - Status: {final_state.get('status')}")
            print(f"   Requires approval: {final_state.get('requires_human_approval')}")
            print(f"   Next checkpoint: {final_state.get('approval_checkpoint')}")
            
            session.refresh_from_db()
            
            if final_state.get('status') == 'completed':
                report_path = final_state.get('report_path')
                print(f"   → Report path from state: {report_path}")
                session.mark_completed(report_path)
                print(f"   ✅ Session marked completed with report: {report_path}")
            elif final_state.get('requires_human_approval'):
                next_checkpoint = final_state.get('approval_checkpoint', 'unknown')
                session.mark_awaiting_approval(next_checkpoint)
                print(f"   ⏸️ Session at next checkpoint: {next_checkpoint}")
            elif final_state.get('status') == 'awaiting_approval':
                next_checkpoint = final_state.get('approval_checkpoint', 'unknown')
                session.mark_awaiting_approval(next_checkpoint)
                print(f"   ⏸️ Session at next checkpoint: {next_checkpoint}")
            elif final_state.get('error'):
                session.mark_failed(final_state.get('error'))
                print(f"   ❌ Session failed")
        except Exception as e:
            logger.error(f"Pipeline resume failed for session {session_id}: {e}")
            print(f"   ❌ Resume exception: {e}")
            traceback.print_exc()
            session.refresh_from_db()
            session.mark_failed(str(e))
    
    thread = threading.Thread(target=resume_pipeline)
    thread.start()
    
    return Response({
        'status': 'processing',
        'session_id': session_id,
        'approved_checkpoint': checkpoint,
        'message': f'Checkpoint {checkpoint} approved, workflow resuming'
    })


@api_view(['GET'])
def get_session_status(request, session_id):
    """
    Get the current status and state of a session.
    Includes draft preview when at a checkpoint.
    
    Returns:
        JSON with session details and preview
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    
    response_data = {
        'session_id': session.id,
        'status': session.status,
        'current_step': session.current_step,
        'requires_approval': session.requires_approval,
        'approval_checkpoint': session.approval_checkpoint,
        'error_message': session.error_message,
        'created_at': session.created_at.isoformat(),
        'updated_at': session.updated_at.isoformat(),
    }
    
    # Add draft preview when awaiting approval
    if session.requires_approval:
        try:
            workflow_state = get_workflow_state(session_id)
            if workflow_state:
                preview = {}
                
                if session.approval_checkpoint == 'extraction_review':
                    # Show extraction results
                    pages = workflow_state.get('pages', [])
                    preview = {
                        'type': 'extraction',
                        'title': 'Document Extraction Results',
                        'pages_count': len(pages),
                        'sample_content': pages[0][:500] + '...' if pages else 'No content extracted',
                        'tables_count': workflow_state.get('table_count', 0),
                    }
                elif session.approval_checkpoint == 'report_approval':
                    # Show FULL analysis results for approval
                    preview = {
                        'type': 'report',
                        'title': 'Full Analysis Report for Approval',
                        # Text summaries
                        'analysis': workflow_state.get('analysis_result', 'No analysis available'),
                        'compliance': workflow_state.get('compliance_result', 'No compliance check'),
                        'risk': workflow_state.get('risk_result', 'No risk assessment'),
                        # Full compliance audit report
                        'audit_report': workflow_state.get('audit_report'),
                        # Full risk assessment report
                        'risk_report': workflow_state.get('risk_report'),
                        # Report file path
                        'report_path': workflow_state.get('report_path'),
                        # Page count
                        'pages_count': len(workflow_state.get('pages', [])),
                    }
                
                response_data['preview'] = preview
        except Exception as e:
            print(f"Failed to get preview: {e}")
    
    # Add report info if completed
    if session.status == 'completed' and session.report_file:
        response_data['report_available'] = True
        response_data['report_url'] = f'/api/sessions/{session_id}/report/'
    
    return Response(response_data)


@api_view(['GET'])
def download_report(request, session_id):
    """
    Returns the generated PDF report as a downloadable file.
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    
    # Debug logging
    print(f"📥 Download request for session {session_id}")
    print(f"   Status: {session.status}")
    print(f"   Report file: {session.report_file}")
    
    if session.status != 'completed':
        return Response({
            'error': 'Report not available',
            'current_status': session.status
        }, status=404)
    
    if not session.report_file:
        return Response({'error': 'Report file not found', 'debug': 'report_file is empty'}, status=404)
    
    try:
        return FileResponse(
            open(session.report_file, 'rb'),
            content_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="report_{session_id}.pdf"'
            }
        )
    except FileNotFoundError:
        return Response({'error': 'Report file not found on disk'}, status=404)


@api_view(['POST'])
def retry_analysis(request, session_id):
    """
    Retry a failed analysis from the last checkpoint.
    
    Returns:
        JSON with status
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    
    if session.status != 'failed':
        return Response({
            'error': 'Can only retry failed sessions',
            'current_status': session.status
        }, status=400)
    
    session.retry_count += 1
    session.error_message = None
    session.mark_processing()
    
    # Recovery = native LangGraph resume. Because the checkpointer is durable,
    # resume_analysis_pipeline() -> ainvoke(None, config) continues from the
    # last successfully-checkpointed node instead of re-running from scratch.
    def retry_pipeline():
        try:
            final_state = resume_analysis_pipeline(session_id)
            
            session.refresh_from_db()
            if final_state.get('status') == 'completed':
                session.mark_completed(final_state.get('report_path'))
            elif final_state.get('status') == 'awaiting_approval':
                session.mark_awaiting_approval(final_state.get('approval_checkpoint'))
            elif final_state.get('error'):
                session.mark_failed(final_state.get('error'))
        except Exception as e:
            logger.error(f"Pipeline retry failed for session {session_id}: {e}")
            session.refresh_from_db()
            session.mark_failed(str(e))
    
    thread = threading.Thread(target=retry_pipeline)
    thread.start()
    
    return Response({
        'status': 'processing',
        'session_id': session_id,
        'retry_count': session.retry_count,
        'message': 'Analysis retry started from last checkpoint'
    })


@api_view(['GET'])
def list_sessions(request):
    """
    List all analysis sessions.
    
    Query params:
        status (optional): Filter by status
        
    Returns:
        JSON list of sessions
    """
    queryset = AnalysisSession.objects.all()
    
    status_filter = request.query_params.get('status')
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    
    sessions = queryset[:50]  # Limit to 50 most recent
    
    return Response({
        'sessions': [
            {
                'session_id': s.id,
                'status': s.status,
                'requires_approval': s.requires_approval,
                'created_at': s.created_at.isoformat(),
            }
            for s in sessions
        ]
    })