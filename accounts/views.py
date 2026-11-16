from datetime import timedelta
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from django.contrib.auth import get_user_model
from .forms import LoginForm
from activity.models import ActivityLog
from companies.models import Company, Department

User = get_user_model()

LOCK_MINUTES = 15
MAX_ATTEMPTS = 5


def is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser or user.role in ('tech_admin', 'company_admin')
    )


@require_http_methods(["GET", "POST", "HEAD"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect('files:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()

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
            email = request.POST.get('username')
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


@login_required
def user_list(request):
    """Liste des utilisateurs — réservé aux admins"""
    if not is_admin_user(request.user):
        messages.error(request, _('Accès réservé aux administrateurs.'))
        return redirect('files:dashboard')

    users = User.objects.all().select_related('company', 'department').order_by('role', 'email')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
@require_http_methods(["GET", "POST"])
def user_edit(request, user_id):
    """Modifier un utilisateur et son mot de passe"""
    if not is_admin_user(request.user):
        messages.error(request, _('Accès réservé aux administrateurs.'))
        return redirect('files:dashboard')

    target = get_object_or_404(User, pk=user_id)
    company = request.user.company or target.company
    departments = Department.objects.filter(company=company, is_active=True).order_by('name') if company else Department.objects.none()

    if request.method == 'POST':
        target.first_name = request.POST.get('first_name', target.first_name).strip()
        target.last_name = request.POST.get('last_name', target.last_name).strip()
        target.email = request.POST.get('email', target.email).strip()
        target.role = request.POST.get('role', target.role)
        target.phone = request.POST.get('phone', target.phone).strip()
        target.is_active = request.POST.get('is_active') == 'on'

        dept_id = request.POST.get('department') or None
        if dept_id:
            try:
                target.department = Department.objects.get(pk=dept_id, company=company)
            except Department.DoesNotExist:
                target.department = None
        else:
            target.department = None

        if company and not target.company_id:
            target.company = company

        # Si manager : le définir comme manager du département
        if target.role == 'manager' and target.department_id:
            target.department.manager = target
            target.department.save(update_fields=['manager'])

        try:
            quota = int(request.POST.get('storage_quota_mb') or target.storage_quota_mb)
            target.storage_quota_mb = max(1, quota)
        except ValueError:
            pass

        new_password = request.POST.get('new_password', '').strip()
        new_password2 = request.POST.get('new_password2', '').strip()
        if new_password:
            if new_password != new_password2:
                messages.error(request, _('Les deux mots de passe ne correspondent pas.'))
                return render(request, 'accounts/user_edit.html', {
                    'target': target, 'roles': User.Role.choices, 'departments': departments,
                })
            if len(new_password) < 6:
                messages.error(request, _('Le mot de passe doit contenir au moins 6 caractères.'))
                return render(request, 'accounts/user_edit.html', {
                    'target': target, 'roles': User.Role.choices, 'departments': departments,
                })
            target.set_password(new_password)
            messages.success(request, _('Mot de passe mis à jour.'))

        target.save()
        messages.success(request, _('Utilisateur mis à jour.'))
        return redirect('accounts:user_list')

    return render(request, 'accounts/user_edit.html', {
        'target': target,
        'roles': User.Role.choices,
        'departments': departments,
    })


@login_required
@require_http_methods(["GET", "POST"])
def user_create(request):
    """Créer un nouvel utilisateur"""
    if not is_admin_user(request.user):
        messages.error(request, _('Accès réservé aux administrateurs.'))
        return redirect('files:dashboard')

    company = request.user.company
    if not company:
        company = Company.objects.first()
    departments = Department.objects.filter(company=company, is_active=True).order_by('name') if company else Department.objects.none()

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        password2 = request.POST.get('password2', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        role = request.POST.get('role', User.Role.EMPLOYEE)
        dept_id = request.POST.get('department') or None

        department = None
        if dept_id:
            try:
                department = Department.objects.get(pk=dept_id, company=company)
            except Department.DoesNotExist:
                department = None

        if not email or not password:
            messages.error(request, _('E-mail et mot de passe obligatoires.'))
        elif password != password2:
            messages.error(request, _('Les deux mots de passe ne correspondent pas.'))
        elif User.objects.filter(email=email).exists():
            messages.error(request, _('Cet e-mail est déjà utilisé.'))
        elif len(password) < 6:
            messages.error(request, _('Le mot de passe doit contenir au moins 6 caractères.'))
        elif role in ('manager', 'employee') and not department:
            messages.error(request, _('Veuillez choisir un département pour ce rôle.'))
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                company=company,
                department=department,
            )
            if role == 'manager' and department:
                department.manager = user
                department.save(update_fields=['manager'])
            messages.success(request, _('Utilisateur %(email)s créé.') % {'email': email})
            return redirect('accounts:user_list')

    return render(request, 'accounts/user_create.html', {
        'roles': User.Role.choices,
        'departments': departments,
    })


@login_required
@require_http_methods(["GET", "POST"])
def department_list(request):
    """Gestion des départements de l'entreprise"""
    if not is_admin_user(request.user):
        messages.error(request, _('Accès réservé aux administrateurs.'))
        return redirect('files:dashboard')

    company = request.user.company or Company.objects.first()
    if not company:
        company = Company.objects.create(name='Mon Entreprise', slug='mon-entreprise')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            Department.objects.get_or_create(
                company=company, name=name,
                defaults={'description': request.POST.get('description', '').strip()}
            )
            messages.success(request, _('Département « %(name)s » créé.') % {'name': name})
            return redirect('accounts:department_list')
        messages.error(request, _('Le nom du département est obligatoire.'))

    departments = Department.objects.filter(company=company).order_by('name')
    return render(request, 'accounts/department_list.html', {
        'departments': departments,
        'company': company,
    })


@login_required
@require_POST
def user_delete(request, user_id):
    if not is_admin_user(request.user):
        messages.error(request, _('Accès réservé aux administrateurs.'))
        return redirect('files:dashboard')
    target = get_object_or_404(User, pk=user_id)
    if target.pk == request.user.pk:
        messages.error(request, _('Vous ne pouvez pas supprimer votre propre compte.'))
        return redirect('accounts:user_list')
    email = target.email
    target.delete()
    messages.success(request, _('Utilisateur %(email)s supprimé.') % {'email': email})
    return redirect('accounts:user_list')
