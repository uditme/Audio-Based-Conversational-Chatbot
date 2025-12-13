from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Session
from .serializers import SessionSerializer

class SessionCreate(APIView):
    """
    POST /api/sessions/
    Request: { "client_info": {...} } (optional)
    Response: { "session_id": "<uuid>" }
    """
    def post(self, request):
        client_info = request.data.get('client_info', {})
        session = Session.objects.create(client_info=client_info)
        return Response({"session_id": str(session.id)}, status=status.HTTP_201_CREATED)

class SessionFinalize(APIView):
    """
    POST /api/sessions/{session_id}/finalize/
    Request: { "final_transcript": "...", "duration_ms": 1234, "chunks": [...] }
    Response: 200 OK
    """
    def post(self, request, session_id):
        session = get_object_or_404(Session, pk=session_id)
        
        final_transcript = request.data.get('final_transcript')
        duration_ms = request.data.get('duration_ms')
        
        # We don't strictly need chunks in the model according to spec, but we accept them
        
        if final_transcript is not None:
            session.final_transcript = final_transcript
        
        if duration_ms is not None:
            session.duration_ms = duration_ms
            
        session.status = "completed"
        session.save()
        
        return Response(status=status.HTTP_200_OK)
