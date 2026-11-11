from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class ActivityLog(models.Model):
    class Action(models.TextChoices):
        LOGIN = 'login', _('Connexion')
        LOGOUT = 'logout', _('Déconnexion')
        UPLOAD = 'upload', _('Téléversement')
        DOWNLOAD = 'download', _('Téléchargement')
        DELETE = 'delete', _('Suppression')
        RESTORE = 'restore', _('Restauration')
        RENAME = 'rename', _('Renommage')
        MOVE = 'move', _('Déplacement')
        SHARE = 'share', _('Partage')
        UNSHARE = 'unshare', _('Annulation de partage')
        PERMISSION_CHANGE = 'perm_change', _('Changement de permission')
        CREATE_FOLDER = 'create_folder', _('Création de dossier')
        VIEW = 'view', _('Consultation')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='activities', verbose_name=_('utilisateur')
    )
    action = models.CharField(max_length=30, choices=Action.choices)
    target_type = models.CharField(max_length=50, blank=True)  # FileItem, Folder, etc.
    target_id = models.PositiveIntegerField(null=True, blank=True)
    target_name = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('journal d\'activité')
        verbose_name_plural = _('journaux d\'activité')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.created_at}"
