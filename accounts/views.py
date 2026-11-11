from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .forms import LoginForm
from activity.models import ActivityLog


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('files:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            if user.failed_login_attempts >= 5:
                messages.error(request, _('Compte temporairement verrouillé suite à trop de tentatives. Contactez un administrateur.'))
                return render(request, 'accounts/login.html', {'form': form})
            login(request, user)
            user.failed_login_attempts = 0
            user.save(update_fields=['failed_login_attempts'])
            ActivityLog.objects.create(
                user=user, action=ActivityLog.Action.LOGIN,
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, _('Bienvenue, %(name)s !') % {'name': user.get_full_name() or user.email})
            next_url = request.GET.get('next') or 'files:dashboard'
            return redirect(next_url)
        else:
            # Track failed attempts
            email = request.POST.get('username')
            from .models import User
            try:
                u = User.objects.get(email=email)
                u.failed_login_attempts += 1
                u.last_failed_login = timezone.now()
                u.save(update_fields=['failed_login_attempts', 'last_failed_login'])
            except User.DoesNotExist:
                pass
            messages.error(request, _('E-mail ou mot de passe incorrect.'))

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    ActivityLog.objects.create(
        user=request.user, action=ActivityLog.Action.LOGOUT,
        ip_address=request.META.get('REMOTE_ADDR')
    )
    logout(request)
    messages.info(request, _('Vous êtes déconnecté.'))
    return redirect('accounts:login')


@login_required
def profile_view(request):
    return render(request, 'accounts/profile.html', {'user': request.user})
