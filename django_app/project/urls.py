from django.contrib import admin
from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/sessions/', views.SessionCreate.as_view(), name='session-create'),
    path('api/sessions/<uuid:session_id>/finalize/', views.SessionFinalize.as_view(), name='session-finalize'),
]

urlpatterns = format_suffix_patterns(urlpatterns)
