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
    """Contrôle d'accès serveur selon les rôles du cahier des charges."""
    if not user.is_authenticated:
        return False
    # 1) Administrateur technique : tout
    if user.is_superuser or user.role == 'tech_admin':
        return True
    # 2) Propriétaire
    if file_item.owner_id == user.id:
        return True
    # 3) Administrateur d'entreprise : fichiers de son entreprise
    if user.role == 'company_admin' and user.company_id:
        if file_item.owner_id and getattr(file_item.owner, 'company_id', None) == user.company_id:
            return True
        if file_item.department_id and getattr(file_item.department, 'company_id', None) == user.company_id:
            return True
    # 4) Manager : fichiers de son département
    if user.role == 'manager' and user.department_id:
        if file_item.department_id == user.department_id:
            return True
        if file_item.owner_id and getattr(file_item.owner, 'department_id', None) == user.department_id:
            return True
    # 5) Permissions explicites (partage interne)
    if Permission.objects.filter(
        Q(user=user) | Q(group__members=user),
        file_item=file_item,
        permission__in=['view', 'download', 'edit', 'manage']
    ).exists():
        return True
    return False


def user_can_access_folder(user, folder):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.role == 'tech_admin':
        return True
    if folder.owner_id == user.id:
        return True
    if user.role == 'company_admin' and user.company_id:
        if folder.owner_id and getattr(folder.owner, 'company_id', None) == user.company_id:
            return True
        if folder.department_id and getattr(folder.department, 'company_id', None) == user.company_id:
            return True
    if user.role == 'manager' and user.department_id:
        if folder.department_id == user.department_id:
            return True
        if folder.owner_id and getattr(folder.owner, 'department_id', None) == user.department_id:
            return True
    return Permission.objects.filter(
        Q(user=user) | Q(group__members=user),
        folder=folder,
        permission__in=['view', 'upload', 'manage']
    ).exists()


def files_queryset_for(user):
    """Fichiers visibles selon le rôle (sans les soft-deleted)."""
    qs = FileItem.objects.filter(is_deleted=False).select_related(
        'owner', 'owner__department', 'department', 'folder'
    )
    role = (user.role or '').strip()
    if user.is_superuser or role == 'tech_admin':
        return qs
    if role == 'company_admin' and user.company_id:
        return qs.filter(
            Q(owner=user) |
            Q(owner__company_id=user.company_id) |
            Q(department__company_id=user.company_id) |
            Q(permissions__user=user)
        ).distinct()
    if role == 'manager':
        if not user.department_id:
            # Manager sans département : uniquement ses fichiers
            return qs.filter(owner=user)
        return qs.filter(
            Q(owner=user) |
            Q(department_id=user.department_id) |
            Q(owner__department_id=user.department_id) |
            Q(permissions__user=user)
        ).distinct()
    # Employé : siens + partagés
    return qs.filter(
        Q(owner=user) | Q(permissions__user=user)
    ).distinct()


def folders_queryset_for(user, parent=None):
    qs = Folder.objects.filter(is_deleted=False, parent=parent).select_related('owner', 'department')
    if user.is_superuser or user.role == 'tech_admin':
        return qs
    if user.role == 'company_admin' and user.company_id:
        return qs.filter(
            Q(owner=user) |
            Q(owner__company_id=user.company_id) |
            Q(department__company_id=user.company_id)
        ).distinct()
    if user.role == 'manager' and user.department_id:
        return qs.filter(
            Q(owner=user) |
            Q(department_id=user.department_id) |
            Q(owner__department_id=user.department_id)
        ).distinct()
    return qs.filter(owner=user)


def file_exists_on_disk(file_item):
    """Vérifie si le fichier existe (disque local ou R2/S3)."""
    try:
        if not file_item.file or not file_item.file.name:
            return False
        from django.conf import settings
        if getattr(settings, 'USE_S3', False):
            # Stockage distant : le fichier est considéré présent si le champ est rempli
            return True
        if hasattr(file_item.file, 'path'):
            return os.path.exists(file_item.file.path)
        return True
    except Exception:
        return False



def cleanup_missing_files(queryset):
    """
    Soft-delete les fichiers dont le contenu a disparu du disque
    (ex: redémarrage Render) et renvoie uniquement ceux encore présents.
    """
    present = []
    for item in queryset:
        if file_exists_on_disk(item):
            present.append(item)
        else:
            if not item.is_deleted:
                item.soft_delete()
    return present


@login_required
def dashboard(request):
    user = request.user
    recent_qs = files_queryset_for(user).order_by('-updated_at')[:30]
    recent_files = cleanup_missing_files(list(recent_qs)[:20])[:8]
    recent_folders = folders_queryset_for(user, parent=None).order_by('-updated_at')[:6]
    shared_qs = FileItem.objects.filter(
        permissions__user=user, is_deleted=False
    ).exclude(owner=user).distinct()[:20]
    shared_with_me = cleanup_missing_files(list(shared_qs))[:5]
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

    folders = folders_queryset_for(user, parent=current_folder)
    if current_folder is None:
        files_qs = files_queryset_for(user).filter(folder__isnull=True)
    else:
        files_qs = files_queryset_for(user).filter(folder=current_folder)

    # Search
    q = request.GET.get('q', '').strip()
    if q:
        folders = folders.filter(name__icontains=q)
        files_qs = files_qs.filter(name__icontains=q)

    # Sort
    sort = request.GET.get('sort', 'name')
    if sort == 'date':
        folders = folders.order_by('-updated_at')
        files_qs = files_qs.order_by('-updated_at')
    elif sort == 'size':
        files_qs = files_qs.order_by('-size')
        folders = folders.order_by('name')
    else:
        folders = folders.order_by('name')
        files_qs = files_qs.order_by('name')

    # Supprimer de la liste (soft-delete) les fichiers absents du disque
    files = cleanup_missing_files(files_qs)

    # Breadcrumb
    breadcrumbs = []
    if current_folder:
        f = current_folder
        while f:
            breadcrumbs.insert(0, f)
            f = f.parent

    scope_note = None
    if user.role == 'manager':
        if user.department_id:
            scope_note = _('Vue Manager — département : %(dept)s') % {'dept': user.department.name}
        else:
            scope_note = _('Attention : aucun département n\'est assigné à votre compte. Vous ne voyez que vos fichiers.')
    elif user.role == 'company_admin':
        scope_note = _('Vue Administrateur entreprise — tous les fichiers de la société')
    elif user.role == 'tech_admin':
        scope_note = _('Vue Administrateur technique — tous les fichiers')

    context = {
        'current_folder': current_folder,
        'folders': folders,
        'files': files,
        'breadcrumbs': breadcrumbs,
        'q': q,
        'sort': sort,
        'scope_note': scope_note,
    }
    return render(request, 'files/browser.html', context)


@login_required
@require_POST
def upload_file(request):
    user = request.user
    try:
        folder_id = request.POST.get('folder_id')
        folder = None
        if folder_id:
            folder = get_object_or_404(Folder, pk=folder_id, is_deleted=False)
            if not user_can_access_folder(user, folder):
                return JsonResponse({'error': _('Accès non autorisé')}, status=403)

        uploaded = request.FILES.getlist('files')
        if not uploaded:
            return JsonResponse({'error': _('Aucun fichier reçu')}, status=400)

        total_size = sum(f.size for f in uploaded)
        if (user.used_storage_bytes + total_size) > (user.storage_quota_mb * 1024 * 1024):
            return JsonResponse({'error': _('Quota de stockage dépassé')}, status=400)

        created = []
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        owner = UserModel.objects.select_related('department').get(pk=user.pk)
        for f in uploaded:
            item = FileItem(
                name=f.name,
                file=f,
                owner=owner,
                folder=folder,
                department=owner.department,
                size=f.size,
            )
            item.save()
            log_activity(user, ActivityLog.Action.UPLOAD, item, request)
            created.append({'id': item.id, 'name': item.name, 'size': item.size_human})

        return JsonResponse({'success': True, 'files': created})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': _('Erreur upload: %(err)s') % {'err': str(e)[:300]}
        }, status=500)


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
    from urllib.parse import quote
    file_item = get_object_or_404(FileItem, pk=file_id, is_deleted=False)
    if not user_can_access_file(request.user, file_item):
        raise Http404

    if not file_item.file or not getattr(file_item.file, 'name', None):
        return HttpResponse(
            '<html><body style="font-family:sans-serif;padding:2rem">'
            '<h2>Fichier introuvable</h2>'
            '<p>Aucune donnée fichier en base.</p>'
            '<a href="/files/browser/">← Retour</a></body></html>',
            status=404, content_type='text/html; charset=utf-8'
        )

    # Fichier physiquement absent (disque éphémère Render)
    try:
        if hasattr(file_item.file, 'path') and not os.path.exists(file_item.file.path):
            return HttpResponse(
                '<html><body style="font-family:sans-serif;padding:2rem">'
                '<h2>Fichier perdu sur le serveur</h2>'
                '<p>Sur le plan gratuit de Render, les fichiers sont effacés après chaque redémarrage.</p>'
                '<p><b>Solution :</b> téléversez le fichier à nouveau, puis cliquez sur télécharger '
                '<u>sans redéployer</u>.</p>'
                '<a href="/files/browser/">← Retour aux fichiers</a></body></html>',
                status=404, content_type='text/html; charset=utf-8'
            )
    except Exception:
        pass

    try:
        log_activity(request.user, ActivityLog.Action.DOWNLOAD, file_item, request)
        f = file_item.file.open('rb')
        response = FileResponse(f, as_attachment=True)
        filename = file_item.name or 'fichier'
        # Compatible ASCII + UTF-8
        response['Content-Disposition'] = (
            f"attachment; filename=\"{filename}\"; "
            f"filename*=UTF-8''{quote(filename)}"
        )
        if file_item.mime_type:
            response['Content-Type'] = file_item.mime_type
        return response
    except FileNotFoundError:
        return HttpResponse(
            '<html><body style="font-family:sans-serif;padding:2rem">'
            '<h2>Fichier absent du disque</h2>'
            '<p>Téléversez-le à nouveau.</p>'
            '<a href="/files/browser/">← Retour</a></body></html>',
            status=404, content_type='text/html; charset=utf-8'
        )
    except Exception as e:
        return HttpResponse(
            f'<html><body style="font-family:sans-serif;padding:2rem">'
            f'<h2>Erreur</h2><pre>{str(e)[:300]}</pre>'
            f'<a href="/files/browser/">← Retour</a></body></html>',
            status=500, content_type='text/html; charset=utf-8'
        )



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
    files_qs = FileItem.objects.filter(
        permissions__user=user, is_deleted=False
    ).distinct()
    files = cleanup_missing_files(files_qs)
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


@login_required
def department_panel(request):
    """
    Manager : son département (membres + fichiers).
    Company admin / tech admin : tous les départements.
    """
    user = request.user
    role = (user.role or '').strip()
    from companies.models import Department
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if role == 'manager':
        if not user.department_id:
            messages.warning(request, _('Aucun département assigné à votre compte.'))
            return redirect('files:dashboard')
        department = user.department
        members = User.objects.filter(
            department=department, is_active=True
        ).order_by('role', 'last_name', 'email')
        files_qs = FileItem.objects.filter(is_deleted=False).filter(
            Q(department=department) | Q(owner__department=department)
        ).select_related('owner', 'folder').order_by('-updated_at')
        files = cleanup_missing_files(list(files_qs[:100]))
        return render(request, 'files/department_panel.html', {
            'department': department,
            'members': members,
            'files': files,
            'is_manager_view': True,
            'departments_data': None,
        })

    if role in ('company_admin', 'tech_admin') or user.is_superuser:
        if role == 'tech_admin' or user.is_superuser:
            departments = Department.objects.all().select_related('company', 'manager').order_by('company__name', 'name')
        elif user.company_id:
            departments = Department.objects.filter(
                company_id=user.company_id
            ).select_related('company', 'manager').order_by('name')
        else:
            departments = Department.objects.all().select_related('company', 'manager').order_by('name')

        departments_data = []
        for dept in departments:
            members = list(
                User.objects.filter(department=dept, is_active=True)
                .order_by('role', 'last_name', 'email')
            )
            files_qs = FileItem.objects.filter(is_deleted=False).filter(
                Q(department=dept) | Q(owner__department=dept)
            ).select_related('owner').order_by('-updated_at')[:50]
            files = cleanup_missing_files(list(files_qs))
            departments_data.append({
                'department': dept,
                'members': members,
                'files': files,
                'member_count': len(members),
                'file_count': len(files),
            })

        return render(request, 'files/department_panel.html', {
            'department': None,
            'members': [],
            'files': [],
            'is_manager_view': False,
            'departments_data': departments_data,
        })

    messages.error(request, _('Accès réservé aux managers et administrateurs.'))
    return redirect('files:dashboard')
