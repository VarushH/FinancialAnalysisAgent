#DRF views for upload, starting the analysis, and returning the report PDF. The start_analysis view spawns a background thread to run the pipeline so the HTTP request can return immediately. Progress and final report info are communicated via the WebSocket consumer and session updates.

import threading
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from .models import AnalysisSession
from .serializers import AnalysisSessionSerializer
from workflows.financial_analysis_workflow import run_analysis_pipeline

# Create your views here.


@api_view(['POST'])
def upload_file(request):
    """
    Accepts a PDF file upload and creates an AnalysisSession.
    """
    parser_classes = (MultiPartParser,)
    file_obj = request.FILES.get('file')
    if not file_obj:
        return Response({'error': 'No file provided'}, status=400)
    session = AnalysisSession.objects.create(file=file_obj)
    return Response({'session_id': session.id})

@api_view(['POST'])
def start_analysis(request, session_id):
    """
    Starts the analysis pipeline in a background thread.
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.status != 'uploaded':
        return Response({'error': 'Analysis already started or completed'}, status=400)
    session.status = 'processing'
    session.save()

    # Run pipeline in a new thread to avoid blocking
    thread = threading.Thread(target=run_analysis_pipeline, args=(session_id,))
    thread.start()
    return Response({'status': 'processing', 'session_id': session_id})

@api_view(['GET'])
def download_report(request, session_id):
    """
    Returns the generated PDF report as a downloadable file.
    """
    session = get_object_or_404(AnalysisSession, pk=session_id)
    if session.status != 'completed' or not session.report_file:
        return Response({'error': 'Report not available'}, status=404)
    return FileResponse(open(session.report_file, 'rb'), content_type='application/pdf',
                        headers={'Content-Disposition': f'attachment; filename="report_{session_id}.pdf"'})