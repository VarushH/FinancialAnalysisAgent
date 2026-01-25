#A simple model to track each analysis session, its uploaded file, status, and generated report path.
from django.db import models

# Create your models here.
class AnalysisSession(models.Model):
    file = models.FileField(upload_to='uploads/')
    status = models.CharField(max_length=20, default='uploaded')  # uploaded, processing, completed
    report_file = models.CharField(max_length=200, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)