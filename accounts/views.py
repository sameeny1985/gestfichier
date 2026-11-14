from datetime import timedelta
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from .forms import LoginForm
from activity.models import ActivityLog


LOCK_MINUTES = 15          # مدت قفل به دقیقه
MAX_ATTEMPTS = 5           # حداکثر تلاش ناموفق


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('files:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()

            # بررسی قفل زمانی
            if user.failed_login_attempts >= MAX_ATTEMPTS and user.last_failed_login:
                unlock_time = user.last_failed_login + timedelta(minutes=LOCK_MINUTES)
                if timezone.now() < unlock_time:
                    remaining = int((unlock_time - timezone.now()).total_seconds() // 60) + 1
                    messages.error(
                        request,
                        _('Compte temporairement verrouillé. Réessayez dans %(min)s minute(s).') % {'min': remaining}
                    )
                    return render(request, 'accounts/login.html', {'form': form})
                else:
                    # زمان قفل گذشته → ریست کن
                    user.failed_login_attempts = 0
                    user.save(update_fields=['failed_login_attempts'])

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
            # ثبت تلاش ناموفق
            email = request.POST.get('username')
            from .models import User
            try:
                u = User.objects.get(email=email)
                u.failed_login_attempts += 1
                u.last_failed_login = timezone.now()
                u.save(update_fields=['failed_login_attempts', 'last_failed_login'])

                if u.failed_login_attempts >= MAX_ATTEMPTS:
                    messages.error(
                        request,
                        _('Compte temporairement verrouillé suite à trop de tentatives. Réessayez dans %(min)s minutes.') % {'min': LOCK_MINUTES}
                    )
                else:
                    messages.error(request, _('E-mail ou mot de passe incorrect.'))
            except User.DoesNotExist:
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
