from rest_framework import serializers
from .models import Session

class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Session
        fields = ['id', 'created_at', 'updated_at', 'client_info', 'status', 'final_transcript', 'duration_ms']
