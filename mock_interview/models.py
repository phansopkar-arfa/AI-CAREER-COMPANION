"""
models.py — Mock Interview Database Models

InterviewSession: Stores each interview attempt with metadata and scores.
QuestionResponse: Stores per-question data (question, answer, score, feedback).
"""

from django.db import models
from django.conf import settings
from django.utils import timezone


class InterviewSession(models.Model):
    """Tracks a complete interview session with scoring and proctoring data."""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('terminated', 'Terminated'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='interview_sessions',
        null=True,
        blank=True,
    )
    domain = models.CharField(max_length=100)
    resume_summary = models.TextField(blank=True, default='')
    total_score = models.FloatField(default=0.0)
    total_questions = models.IntegerField(default=0)
    tab_switches = models.IntegerField(default=0)
    face_violations = models.IntegerField(default=0)
    time_used = models.IntegerField(default=0)  # seconds
    analysis_text = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Interview #{self.pk} — {self.domain} ({self.status})"

    def compute_average_score(self):
        """Calculate average score from all question responses."""
        responses = self.responses.all()
        if not responses.exists():
            return 0.0
        return round(sum(r.score for r in responses) / responses.count(), 1)


class QuestionResponse(models.Model):
    """Stores a single question-answer pair with evaluation data."""

    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    question_number = models.IntegerField()
    question_text = models.TextField()
    answer_text = models.TextField(blank=True, default='')
    score = models.IntegerField(default=0)  # 0-10
    feedback = models.TextField(blank=True, default='')
    strengths_text = models.TextField(default='[]', blank=True)
    improvements_text = models.TextField(default='[]', blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def strengths(self):
        import json
        try:
            return json.loads(self.strengths_text or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    @strengths.setter
    def strengths(self, value):
        import json
        self.strengths_text = json.dumps(value) if isinstance(value, list) else '[]'

    @property
    def improvements(self):
        import json
        try:
            return json.loads(self.improvements_text or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    @improvements.setter
    def improvements(self, value):
        import json
        self.improvements_text = json.dumps(value) if isinstance(value, list) else '[]'

    class Meta:
        ordering = ['question_number']

    def __str__(self):
        return f"Q{self.question_number} — Score: {self.score}/10"


class ProctoringViolation(models.Model):
    """Logs individual proctoring violation events (tab-switch, multi-face, etc.)."""

    VIOLATION_TYPES = [
        ('tab_switch', 'Tab Switch'),
        ('multi_face', 'Multiple Faces'),
    ]

    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name='proctoring_violations',
    )
    violation_type = models.CharField(max_length=20, choices=VIOLATION_TYPES)
    details = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_violation_type_display()} — Session #{self.session_id}"
