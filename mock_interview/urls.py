from django.urls import path
from . import views

urlpatterns = [
    # Template view
    path('', views.interview_page, name='mock_interview_page'),

    # JSON API endpoints
    path('api/start/', views.api_start_interview, name='mock_interview_start'),
    path('api/answer/', views.api_answer_question, name='mock_interview_answer'),
    path('api/end/', views.api_end_interview, name='mock_interview_end'),
    path('api/pause/', views.api_pause_interview, name='mock_interview_pause'),
    path('api/violation/', views.api_report_violation, name='mock_interview_violation'),
    path('api/face-violation/', views.api_face_violation, name='mock_interview_face_violation'),
    
    # Dashboard & Reporting endpoints
    path('api/history/', views.api_history, name='mock_interview_history'),
    path('api/dashboard/', views.api_dashboard, name='mock_interview_dashboard'),
    path('api/pdf/<int:session_id>/', views.api_pdf_report, name='mock_interview_pdf'),
]
