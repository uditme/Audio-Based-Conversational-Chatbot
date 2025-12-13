from django.contrib import admin
from .models import Session

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'duration_ms')
    list_filter = ('status', 'created_at')
    search_fields = ('id', 'final_transcript')
