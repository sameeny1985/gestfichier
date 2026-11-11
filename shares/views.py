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
    file_item = get_object_or_404(FileItem, pk=file_id, owner=user, is_deleted=False)

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
        details={'token': share.token[:8]},
        ip_address=request.META.get('REMOTE_ADDR')
    )
    messages.success(request, _('Lien de partage créé avec succès.'))
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
