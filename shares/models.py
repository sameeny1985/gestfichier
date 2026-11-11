import secrets
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


def generate_token():
    return secrets.token_urlsafe(32)


class ShareLink(models.Model):
    """Lien de partage externe"""
    token = models.CharField(max_length=64, unique=True, default=generate_token, editable=False)
    file_item = models.ForeignKey(
        'files.FileItem', on_delete=models.CASCADE, null=True, blank=True,
        related_name='share_links'
    )
    folder = models.ForeignKey(
        'files.Folder', on_delete=models.CASCADE, null=True, blank=True,
        related_name='share_links'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='created_shares'
    )
    password = models.CharField(_('mot de passe'), max_length=128, blank=True)
    expires_at = models.DateTimeField(_('expire le'), null=True, blank=True)
    max_downloads = models.PositiveIntegerField(_('téléchargements max'), null=True, blank=True)
    download_count = models.PositiveIntegerField(default=0)
    allow_download = models.BooleanField(_('autoriser le téléchargement'), default=True)
    is_active = models.BooleanField(_('actif'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_accessed = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _('lien de partage')
        verbose_name_plural = _('liens de partage')
        ordering = ['-created_at']

    def __str__(self):
        target = self.file_item.name if self.file_item else (self.folder.name if self.folder else '?')
        return f"Share: {target} ({self.token[:8]}...)"

    @property
    def is_expired(self):
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        if self.max_downloads is not None and self.download_count >= self.max_downloads:
            return True
        return False

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired

    def record_access(self):
        self.download_count += 1
        self.last_accessed = timezone.now()
        self.save(update_fields=['download_count', 'last_accessed'])


class ShareAccessLog(models.Model):
    """Journal des accès externes"""
    share_link = models.ForeignKey(ShareLink, on_delete=models.CASCADE, related_name='access_logs')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)

    class Meta:
        verbose_name = _('accès partage')
        verbose_name_plural = _('accès partages')
        ordering = ['-accessed_at']
