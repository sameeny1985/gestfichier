from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import User


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label=_('Adresse e-mail'),
        widget=forms.EmailInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'email@entreprise.com',
            'autocomplete': 'email'
        })
    )
    password = forms.CharField(
        label=_('Mot de passe'),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '••••••••',
            'autocomplete': 'current-password'
        })
    )


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'company', 'department', 'phone')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'company': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }
