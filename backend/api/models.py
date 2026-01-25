# backend/api/models.py
"""
Models for the financial analysis API.
Tracks analysis sessions with support for workflow checkpoints.
"""

from django.db import models


class AnalysisSession(models.Model):
    """
    Represents a financial document analysis session.
    Tracks the uploaded file, workflow status, and generated report.
    """
    
    # Status choices for the workflow
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('awaiting_approval', 'Awaiting Approval'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    # File and report paths
    file = models.FileField(upload_to='uploads/')
    report_file = models.CharField(max_length=200, blank=True, null=True)
    
    # Workflow status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    current_step = models.CharField(max_length=50, blank=True, null=True)
    
    # Checkpoint support for state persistence
    checkpoint_id = models.CharField(max_length=100, blank=True, null=True)
    requires_approval = models.BooleanField(default=False)
    approval_checkpoint = models.CharField(max_length=50, blank=True, null=True)
    
    # Error tracking
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Session {self.id} - {self.status}"
    
    def mark_processing(self):
        """Mark session as processing."""
        self.status = 'processing'
        self.save(update_fields=['status', 'updated_at'])
    
    def mark_awaiting_approval(self, checkpoint: str):
        """Mark session as awaiting human approval."""
        self.status = 'awaiting_approval'
        self.requires_approval = True
        self.approval_checkpoint = checkpoint
        self.save(update_fields=['status', 'requires_approval', 'approval_checkpoint', 'updated_at'])
    
    def mark_completed(self, report_path: str = None):
        """Mark session as completed."""
        self.status = 'completed'
        self.requires_approval = False
        if report_path:
            self.report_file = report_path
        self.save(update_fields=['status', 'requires_approval', 'report_file', 'updated_at'])
    
    def mark_failed(self, error: str):
        """Mark session as failed with error message."""
        self.status = 'failed'
        self.error_message = error
        self.save(update_fields=['status', 'error_message', 'updated_at'])
    
    def approve_checkpoint(self):
        """Clear approval requirement and continue."""
        self.requires_approval = False
        self.approval_checkpoint = None
        self.status = 'processing'
        self.save(update_fields=['requires_approval', 'approval_checkpoint', 'status', 'updated_at'])