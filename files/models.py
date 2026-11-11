import os
import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


def file_upload_path(instance, filename):
    """Chemin d'upload sécurisé : company/year/month/uuid_filename"""
    ext = filename.split('.')[-1] if '.' in filename else ''
    new_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    company_id = instance.owner.company_id or 'global'
    return f"files/{company_id}/{timezone.now().year}/{timezone.now().month:02d}/{new_name}"


class Folder(models.Model):
    name = models.CharField(_('nom'), max_length=255)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='subfolders', verbose_name=_('dossier parent')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='folders', verbose_name=_('propriétaire')
    )
    department = models.ForeignKey(
        'companies.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='folders', verbose_name=_('département')
    )
    is_shared = models.BooleanField(_('partagé'), default=False)
    is_deleted = models.BooleanField(_('supprimé'), default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('dossier')
        verbose_name_plural = _('dossiers')
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_path(self):
        parts = [self.name]
        p = self.parent
        while p:
            parts.insert(0, p.name)
            p = p.parent
        return ' / '.join(parts)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])
        # Soft delete children recursively
        for sub in self.subfolders.filter(is_deleted=False):
            sub.soft_delete()
        for f in self.files.filter(is_deleted=False):
            f.soft_delete()


class FileItem(models.Model):
    """Fichier stocké (avec versioning simple)"""
    name = models.CharField(_('nom'), max_length=255)
    file = models.FileField(_('fichier'), upload_to=file_upload_path)
    size = models.BigIntegerField(_('taille (octets)'), default=0)
    mime_type = models.CharField(_('type MIME'), max_length=100, blank=True)
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True,
        related_name='files', verbose_name=_('dossier')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='files', verbose_name=_('propriétaire')
    )
    department = models.ForeignKey(
        'companies.Department', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='files', verbose_name=_('département')
    )
    version = models.PositiveIntegerField(_('version'), default=1)
    is_deleted = models.BooleanField(_('supprimé'), default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(_('description'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('fichier')
        verbose_name_plural = _('fichiers')
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.file and not self.size:
            try:
                self.size = self.file.size
            except Exception:
                pass
        if self.file and not self.mime_type:
            import mimetypes
            self.mime_type = mimetypes.guess_type(self.name)[0] or 'application/octet-stream'
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    @property
    def extension(self):
        return os.path.splitext(self.name)[1].lower()

    @property
    def size_human(self):
        size = self.size
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} To"


class FileVersion(models.Model):
    """Historique des versions d'un fichier"""
    file_item = models.ForeignKey(
        FileItem, on_delete=models.CASCADE, related_name='versions',
        verbose_name=_('fichier')
    )
    version_number = models.PositiveIntegerField(_('numéro de version'))
    file = models.FileField(_('fichier'), upload_to=file_upload_path)
    size = models.BigIntegerField(default=0)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    comment = models.CharField(_('commentaire'), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('version de fichier')
        verbose_name_plural = _('versions de fichiers')
        ordering = ['-version_number']
        unique_together = [['file_item', 'version_number']]

    def __str__(self):
        return f"{self.file_item.name} v{self.version_number}"


class Permission(models.Model):
    """Permissions granulaires sur dossiers/fichiers"""
    class PermType(models.TextChoices):
        VIEW = 'view', _('Voir')
        DOWNLOAD = 'download', _('Télécharger')
        UPLOAD = 'upload', _('Téléverser')
        EDIT = 'edit', _('Modifier')
        RENAME = 'rename', _('Renommer')
        MOVE = 'move', _('Déplacer')
        DELETE = 'delete', _('Supprimer')
        SHARE = 'share', _('Partager')
        MANAGE = 'manage', _('Gérer les accès')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='file_permissions'
    )
    group = models.ForeignKey(
        'companies.Group', on_delete=models.CASCADE, null=True, blank=True,
        related_name='file_permissions'
    )
    folder = models.ForeignKey(
        Folder, on_delete=models.CASCADE, null=True, blank=True,
        related_name='permissions'
    )
    file_item = models.ForeignKey(
        FileItem, on_delete=models.CASCADE, null=True, blank=True,
        related_name='permissions'
    )
    permission = models.CharField(max_length=20, choices=PermType.choices)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='granted_permissions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')

    def __str__(self):
        target = self.folder or self.file_item
        who = self.user or self.group
        return f"{who} - {self.permission} sur {target}"
