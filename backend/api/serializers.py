# backend/api/serializers.py
"""
Serializers for the financial analysis API.
"""

from rest_framework import serializers
from .models import AnalysisSession


class AnalysisSessionSerializer(serializers.ModelSerializer):
    """Serializer for AnalysisSession model."""
    
    class Meta:
        model = AnalysisSession
        fields = [
            'id',
            'file',
            'status',
            'current_step',
            'requires_approval',
            'approval_checkpoint',
            'error_message',
            'report_file',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'status',
            'current_step',
            'requires_approval',
            'approval_checkpoint',
            'error_message',
            'report_file',
            'created_at',
            'updated_at',
        ]


class ApprovalSerializer(serializers.Serializer):
    """Serializer for checkpoint approval requests."""
    
    feedback = serializers.CharField(required=False, allow_blank=True)


class WorkflowStateSerializer(serializers.Serializer):
    """Serializer for workflow state responses."""
    
    session_id = serializers.IntegerField()
    status = serializers.CharField()
    current_agent = serializers.CharField(allow_null=True)
    requires_approval = serializers.BooleanField()
    approval_checkpoint = serializers.CharField(allow_null=True)
    messages = serializers.ListField(child=serializers.DictField())