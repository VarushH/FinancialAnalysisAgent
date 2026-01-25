#A serializer for the upload endpoint (to save the file).

from rest_framework import serializers
from .models import AnalysisSession

class AnalysisSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalysisSession
        fields = ['id', 'file', 'status', 'report_file']