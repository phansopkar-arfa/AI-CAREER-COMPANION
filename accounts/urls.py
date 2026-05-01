from django.urls import path
from . import views
from . import coach_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('demo/', views.demo_view, name='demo'),
    path('password-reset/', views.password_reset_request, name='password_reset'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password_reset_confirm'),
    path('password-reset/resend-otp/', views.resend_otp, name='resend_otp'),
    path('ats-evaluator/', views.home, name='ats_evaluator'),
    # Test & Evaluation
    path('career-test/', views.career_test, name='career_test'),
    path('test-info/<slug:subject_slug>/', views.test_info, name='test_info'),
    path('start-test/<slug:subject_slug>/', views.start_test, name='start_test'),
    path('submit-test/<slug:subject_slug>/', views.submit_test, name='submit_test'),
    path('dashboard/', views.dashboard, name='dashboard'),
    # AI Resume Generator
    path('resume/editor/', views.resume_editor, name='resume_editor'),
    path('resume/preview-fragment/', views.resume_preview_fragment, name='resume_preview_fragment'),
    path('resume/ai-summary/', views.resume_ai_summary, name='resume_ai_summary'),
    path('resume/ats-match/', views.resume_ats_match, name='resume_ats_match'),
    path('resume/tone-adjust/', views.resume_tone_adjust, name='resume_tone_adjust'),
    path('resume/star-polish/', views.resume_star_polish, name='resume_star_polish'),
    path('resume/recommend-skills/', views.resume_recommend_skills, name='resume_recommend_skills'),
    path('resume/save-json/', views.resume_save, name='resume_save'),
    path('resume/download/', views.resume_download_pdf, name='resume_download'),
    # AI Career Coach API
    path('api/coach/chat/', coach_views.coach_chat, name='coach_chat'),
    path('api/coach/quick-action/', coach_views.coach_quick_action, name='coach_quick_action'),
    path('api/coach/history/', coach_views.coach_history, name='coach_history'),
    path('api/coach/clear/', coach_views.coach_clear_history, name='coach_clear_history'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)