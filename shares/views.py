from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from .models import ShareLink, ShareAccessLog
from files.models import FileItem
from activity.models import ActivityLog


@login_required
@require_POST
def create_share(request):
    user = request.user
    file_id = request.POST.get('file_id')
    # Propriétaire ou admin peut partager
    file_item = get_object_or_404(FileItem, pk=file_id, is_deleted=False)
    if file_item.owner_id != user.id and user.role not in ('tech_admin', 'company_admin', 'manager') and not user.is_superuser:
        messages.error(request, _('Vous ne pouvez partager que vos propres fichiers.'))
        return redirect('files:browser')

    share_mode = request.POST.get('share_mode', 'external')  # internal | external

    # --- Partage interne vers un utilisateur du site ---
    if share_mode == 'internal':
        from django.contrib.auth import get_user_model
        from files.models import Permission
        User = get_user_model()
        email = request.POST.get('share_with_email', '').strip().lower()
        if not email:
            messages.error(request, _('Indiquez l\'e-mail de l\'utilisateur.'))
            return redirect(request.META.get('HTTP_REFERER', 'files:browser'))
        try:
            target = User.objects.get(email__iexact=email, is_active=True)
        except User.DoesNotExist:
            messages.error(request, _('Aucun utilisateur avec cet e-mail : %(email)s') % {'email': email})
            return redirect(request.META.get('HTTP_REFERER', 'files:browser'))
        if target.pk == user.pk:
            messages.error(request, _('Vous ne pouvez pas partager avec vous-même.'))
            return redirect(request.META.get('HTTP_REFERER', 'files:browser'))

        for perm in ('view', 'download'):
            Permission.objects.get_or_create(
                user=target,
                file_item=file_item,
                permission=perm,
                defaults={'granted_by': user},
            )
        ActivityLog.objects.create(
            user=user, action=ActivityLog.Action.SHARE,
            target_type='FileItem', target_id=file_item.id,
            target_name=file_item.name,
            details={'to': email, 'mode': 'internal'},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        messages.success(
            request,
            _('Fichier partagé avec %(email)s. Il apparaîtra dans « Partagés ».') % {'email': email}
        )
        return redirect('files:shared')

    # --- Lien externe (public) ---
    password = request.POST.get('password', '').strip()
    days = request.POST.get('expires_days')
    max_dl = request.POST.get('max_downloads')

    expires_at = None
    if days:
        try:
            expires_at = timezone.now() + timedelta(days=int(days))
        except ValueError:
            pass

    max_downloads = None
    if max_dl:
        try:
            max_downloads = int(max_dl)
        except ValueError:
            pass

    share = ShareLink.objects.create(
        file_item=file_item,
        created_by=user,
        password=password,
        expires_at=expires_at,
        max_downloads=max_downloads,
    )
    ActivityLog.objects.create(
        user=user, action=ActivityLog.Action.SHARE,
        target_type='FileItem', target_id=file_item.id,
        target_name=file_item.name,
        details={'token': share.token[:8], 'mode': 'external'},
        ip_address=request.META.get('REMOTE_ADDR')
    )
    messages.success(request, _('Lien de partage créé. Voir « Liens externes ».'))
    return redirect('shares:my_shares')


@login_required
def my_shares(request):
    shares = ShareLink.objects.filter(created_by=request.user).select_related('file_item')
    return render(request, 'shares/my_shares.html', {'shares': shares})


@login_required
@require_POST
def revoke_share(request, share_id):
    share = get_object_or_404(ShareLink, pk=share_id, created_by=request.user)
    share.is_active = False
    share.save(update_fields=['is_active'])
    messages.success(request, _('Lien de partage révoqué.'))
    return redirect('shares:my_shares')


def public_share(request, token):
    """Accès public au lien de partage (sans compte)"""
    share = get_object_or_404(ShareLink, token=token)
    if not share.is_valid:
        return render(request, 'shares/expired.html', {'share': share})

    # Password check
    if share.password:
        if request.method == 'POST':
            if request.POST.get('password') != share.password:
                messages.error(request, _('Mot de passe incorrect.'))
                return render(request, 'shares/password.html', {'share': share})
        else:
            return render(request, 'shares/password.html', {'share': share})

    if request.GET.get('download') == '1' and share.allow_download and share.file_item:
        share.record_access()
        ShareAccessLog.objects.create(
            share_link=share,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
        )
        return FileResponse(
            share.file_item.file.open('rb'),
            as_attachment=True,
            filename=share.file_item.name
        )

    return render(request, 'shares/public.html', {'share': share})
