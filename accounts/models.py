import json as json_module
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.conf import settings

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email must be provided")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True')
        return self.create_user(email, password, **extra_fields)

class UserProfile(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    registration = models.CharField(max_length=50, blank=True)
    branch = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    passing_year_10 = models.CharField(max_length=4, blank=True)
    percentage_10 = models.CharField(max_length=10, blank=True)
    education = models.CharField(max_length=20, blank=True)
    passing_year_12 = models.CharField(max_length=4, blank=True)
    percentage_12 = models.CharField(max_length=10, blank=True)
    passing_year_diploma = models.CharField(max_length=4, blank=True)
    percentage_diploma = models.CharField(max_length=10, blank=True)
    
    resume_file = models.FileField(upload_to='resumes/', null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email
        
class Subject(models.Model):
    CATEGORY_CHOICES = (
        ('technical', 'Technical'),
        ('company', 'Company'),
        ('aptitude', 'Aptitude'),
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, default='')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='technical')
    icon = models.CharField(max_length=10, default='📚')

    def __str__(self):
        return self.name


class Question(models.Model):
    DIFFICULTY_CHOICES = (
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    correct_answer = models.CharField(max_length=1)
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')

    def __str__(self):
        return f"{self.subject.name} - {self.question_text[:40]}"


class TestResult(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.IntegerField()
    total_questions = models.IntegerField()
    percentage = models.FloatField()
    time_taken = models.IntegerField(default=0)  # seconds
    violations = models.IntegerField(default=0)
    tab_switches = models.IntegerField(default=0)
    auto_submitted = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.subject.name}"


class Resume(models.Model):
    STYLE_CHOICES = (
        ('modernist', 'The Modernist'),
        ('executive', 'The Executive'),
        ('creative', 'The Creative'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='resumes'
    )
    title = models.CharField(max_length=200, default='My Resume')
    style_choice = models.CharField(
        max_length=20,
        choices=STYLE_CHOICES,
        default='modernist'
    )
    resume_json_text = models.TextField(default='{}', blank=True)
    brand_color = models.CharField(max_length=7, default='#6366f1')
    ats_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.email} - {self.title}"

    @property
    def resume_json(self):
        try:
            return json_module.loads(self.resume_json_text or '{}')
        except (json_module.JSONDecodeError, TypeError):
            return {}

    @resume_json.setter
    def resume_json(self, value):
        self.resume_json_text = json_module.dumps(value) if isinstance(value, dict) else '{}'

    @staticmethod
    def get_default_json():
        return {
            "basics": {
                "name": "",
                "email": "",
                "phone": "",
                "linkedin": "",
                "address": "",
                "summary": "",
                "photo": ""
            },
            "skills": {
                "technical": [],
                "soft": []
            },
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "languages": [],
            "extracurricular": [],
            "interests": []
        }


class ChatMessage(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.email} [{self.role}] {self.content[:50]}"

class CareerRoadmap(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='roadmaps')
    dream_role = models.CharField(max_length=200)
    roadmap_json_text = models.TextField(default='[]', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.dream_role}"

    @property
    def roadmap_data(self):
        try:
            return json_module.loads(self.roadmap_json_text)
        except (json_module.JSONDecodeError, TypeError):
            return []