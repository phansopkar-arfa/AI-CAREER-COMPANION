from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import UserProfile

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = UserProfile
        fields = (
            'email', 'name', 'registration', 'branch', 'phone',
            'passing_year_10', 'percentage_10', 'education',
            'passing_year_12', 'percentage_12', 'passing_year_diploma', 'percentage_diploma'
        )

class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = UserProfile
        fields = ('email', 'password')

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError("This account is inactive.")
