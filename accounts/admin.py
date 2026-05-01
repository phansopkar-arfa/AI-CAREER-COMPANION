from django.contrib import admin
from .models import UserProfile, Subject, Question, TestResult, Resume


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'branch', 'is_active', 'is_staff')
    search_fields = ('email', 'name', 'registration')
    list_filter = ('branch', 'is_active', 'is_staff')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'category', 'icon')
    list_filter = ('category',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('subject', 'question_text_short', 'correct_answer', 'difficulty')
    list_filter = ('subject', 'difficulty')
    search_fields = ('question_text',)

    def question_text_short(self, obj):
        return obj.question_text[:60]
    question_text_short.short_description = 'Question'


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ('user', 'subject', 'score', 'total_questions', 'percentage', 'violations', 'date')
    list_filter = ('subject', 'date')
    search_fields = ('user__email',)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'style_choice', 'ats_score', 'updated_at')
    list_filter = ('style_choice',)
    search_fields = ('user__email', 'title')