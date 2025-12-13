from django.db import models
from uuid import uuid4

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    client_info = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=32, default="listening")
    final_transcript = models.TextField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"Session {self.id} ({self.status})"
