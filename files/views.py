import os
import zipfile
from io import BytesIO
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q
from django.core.paginator import Paginator
from .models import Folder, FileItem, FileVersion, Permission
from activity.models import ActivityLog
from shares.models import ShareLink


def log_activity(user, action, target=None, request=None, details=None):
    ActivityLog.objects.create(
        user=user,
        action=action,
        target_type=target.__class__.__name__ if target else '',
        target_id=target.pk if target else None,
        target_name=str(target) if target else '',
        details=details or {},
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
    )


def user_can_access_file(user, file_item):
    """Vérification côté serveur des permissions"""
    if user.is_superuser or user.role == 'tech_admin':
        return True
    if file_item.owner_id == user.id:
        return True
    if file_item.department and user.department_id == file_item.department_id:
        if user.role in ('company_admin', 'manager'):
            return True
    # Check explicit permissions
    if Permission.objects.filter(
        Q(user=user) | Q(group__members=user),
        file_item=file_item,
        permission__in=['view', 'download', 'edit', 'manage']
    ).exists():
        return True
    return False


def user_can_access_folder(user, folder):
    if user.is_superuser or user.role == 'tech_admin':
        return True
    if folder.owner_id == user.id:
        return True
    if folder.department and user.department_id == folder.department_id:
        if user.role in ('company_admin', 'manager'):
            return True
    return Permission.objects.filter(
        Q(user=user) | Q(group__members=user),
        folder=folder,
        permission__in=['view', 'upload', 'manage']
    ).exists()


@login_required
def dashboard(request):
    user = request.user
    recent_files = FileItem.objects.filter(
        owner=user, is_deleted=False
    ).order_by('-updated_at')[:8]
    recent_folders = Folder.objects.filter(
        owner=user, is_deleted=False, parent=None
    ).order_by('-updated_at')[:6]
    shared_with_me = FileItem.objects.filter(
        permissions__user=user, is_deleted=False
    ).distinct()[:5]
    trash_count = FileItem.objects.filter(owner=user, is_deleted=True).count()
    context = {
        'recent_files': recent_files,
        'recent_folders': recent_folders,
        'shared_with_me': shared_with_me,
        'trash_count': trash_count,
        'storage_used': user.used_storage_mb,
        'storage_quota': user.storage_quota_mb,
        'storage_percent': user.storage_usage_percent,
    }
    return render(request, 'files/dashboard.html', context)


@login_required
def file_browser(request, folder_id=None):
    user = request.user
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(Folder, pk=folder_id, is_deleted=False)
        if not user_can_access_folder(user, current_folder):
            messages.error(request, _('Accès non autorisé à ce dossier.'))
            return redirect('files:browser')

    folders = Folder.objects.filter(
        owner=user, is_deleted=False, parent=current_folder
    )
    files = FileItem.objects.filter(
        owner=user, is_deleted=False, folder=current_folder
    )

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        folders = folders.filter(name__icontains=q)
        files = files.filter(name__icontains=q)

    # Sort
    sort = request.GET.get('sort', 'name')
    if sort == 'date':
        folders = folders.order_by('-updated_at')
        files = files.order_by('-updated_at')
    elif sort == 'size':
        files = files.order_by('-size')
        folders = folders.order_by('name')
    else:
        folders = folders.order_by('name')
        files = files.order_by('name')

    # Breadcrumb
    breadcrumbs = []
    if current_folder:
        f = current_folder
        while f:
            breadcrumbs.insert(0, f)
            f = f.parent

    context = {
        'current_folder': current_folder,
        'folders': folders,
        'files': files,
        'breadcrumbs': breadcrumbs,
        'q': q,
        'sort': sort,
    }
    return render(request, 'files/browser.html', context)


@login_required
@require_POST
def upload_file(request):
    user = request.user
    folder_id = request.POST.get('folder_id')
    folder = None
    if folder_id:
        folder = get_object_or_404(Folder, pk=folder_id, is_deleted=False)
        if not user_can_access_folder(user, folder):
            return JsonResponse({'error': _('Accès non autorisé')}, status=403)

    uploaded = request.FILES.getlist('files')
    if not uploaded:
        return JsonResponse({'error': _('Aucun fichier reçu')}, status=400)

    # Check quota
    total_size = sum(f.size for f in uploaded)
    if (user.used_storage_bytes + total_size) > (user.storage_quota_mb * 1024 * 1024):
        return JsonResponse({'error': _('Quota de stockage dépassé')}, status=400)

    created = []
    for f in uploaded:
        item = FileItem(
            name=f.name,
            file=f,
            owner=user,
            folder=folder,
            department=user.department,
            size=f.size,
        )
        item.save()
        log_activity(user, ActivityLog.Action.UPLOAD, item, request)
        created.append({'id': item.id, 'name': item.name, 'size': item.size_human})

    return JsonResponse({'success': True, 'files': created})


@login_required
@require_POST
def create_folder(request):
    user = request.user
    name = request.POST.get('name', '').strip()
    parent_id = request.POST.get('parent_id')
    if not name:
        messages.error(request, _('Le nom du dossier est requis.'))
        return redirect(request.META.get('HTTP_REFERER', 'files:browser'))

    parent = None
    if parent_id:
        parent = get_object_or_404(Folder, pk=parent_id, is_deleted=False)
        if not user_can_access_folder(user, parent):
            messages.error(request, _('Accès non autorisé.'))
            return redirect('files:browser')

    folder = Folder.objects.create(
        name=name, parent=parent, owner=user, department=user.department
    )
    log_activity(user, ActivityLog.Action.CREATE_FOLDER, folder, request)
    messages.success(request, _('Dossier « %(name)s » créé.') % {'name': name})
    if parent:
        return redirect('files:browser_folder', folder_id=parent.id)
    return redirect('files:browser')


@login_required
def download_file(request, file_id):
    file_item = get_object_or_404(FileItem, pk=file_id, is_deleted=False)
    if not user_can_access_file(request.user, file_item):
        raise Http404
    log_activity(request.user, ActivityLog.Action.DOWNLOAD, file_item, request)
    response = FileResponse(file_item.file.open('rb'), as_attachment=True, filename=file_item.name)
    return response


@login_required
@require_POST
def delete_item(request):
    user = request.user
    item_type = request.POST.get('type')
    item_id = request.POST.get('id')
    if item_type == 'file':
        item = get_object_or_404(FileItem, pk=item_id, owner=user, is_deleted=False)
        item.soft_delete()
        log_activity(user, ActivityLog.Action.DELETE, item, request)
        messages.success(request, _('Fichier déplacé dans la corbeille.'))
    elif item_type == 'folder':
        item = get_object_or_404(Folder, pk=item_id, owner=user, is_deleted=False)
        item.soft_delete()
        log_activity(user, ActivityLog.Action.DELETE, item, request)
        messages.success(request, _('Dossier déplacé dans la corbeille.'))
    return redirect(request.META.get('HTTP_REFERER', 'files:browser'))


@login_required
def trash(request):
    user = request.user
    files = FileItem.objects.filter(owner=user, is_deleted=True).order_by('-deleted_at')
    folders = Folder.objects.filter(owner=user, is_deleted=True).order_by('-deleted_at')
    return render(request, 'files/trash.html', {'files': files, 'folders': folders})


@login_required
@require_POST
def restore_item(request):
    user = request.user
    item_type = request.POST.get('type')
    item_id = request.POST.get('id')
    if item_type == 'file':
        item = get_object_or_404(FileItem, pk=item_id, owner=user, is_deleted=True)
        item.restore()
        log_activity(user, ActivityLog.Action.RESTORE, item, request)
        messages.success(request, _('Fichier restauré.'))
    elif item_type == 'folder':
        item = get_object_or_404(Folder, pk=item_id, owner=user, is_deleted=True)
        item.is_deleted = False
        item.deleted_at = None
        item.save()
        log_activity(user, ActivityLog.Action.RESTORE, item, request)
        messages.success(request, _('Dossier restauré.'))
    return redirect('files:trash')


@login_required
def shared_files(request):
    user = request.user
    files = FileItem.objects.filter(
        permissions__user=user, is_deleted=False
    ).distinct()
    return render(request, 'files/shared.html', {'files': files})


@login_required
@require_POST
def rename_item(request):
    user = request.user
    item_type = request.POST.get('type')
    item_id = request.POST.get('id')
    new_name = request.POST.get('name', '').strip()
    if not new_name:
        messages.error(request, _('Nom invalide.'))
        return redirect(request.META.get('HTTP_REFERER', 'files:browser'))
    if item_type == 'file':
        item = get_object_or_404(FileItem, pk=item_id, owner=user, is_deleted=False)
        item.name = new_name
        item.save(update_fields=['name', 'updated_at'])
        log_activity(user, ActivityLog.Action.RENAME, item, request)
    elif item_type == 'folder':
        item = get_object_or_404(Folder, pk=item_id, owner=user, is_deleted=False)
        item.name = new_name
        item.save(update_fields=['name', 'updated_at'])
        log_activity(user, ActivityLog.Action.RENAME, item, request)
    messages.success(request, _('Renommé avec succès.'))
    return redirect(request.META.get('HTTP_REFERER', 'files:browser'))
