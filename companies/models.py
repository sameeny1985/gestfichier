from django.db import models
from django.utils.translation import gettext_lazy as _


class Company(models.Model):
    name = models.CharField(_('nom'), max_length=200)
    slug = models.SlugField(unique=True)
    description = models.TextField(_('description'), blank=True)
    logo = models.ImageField(_('logo'), upload_to='company_logos/', blank=True, null=True)
    storage_quota_gb = models.PositiveIntegerField(_('quota de stockage (Go)'), default=100)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('entreprise')
        verbose_name_plural = _('entreprises')
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def used_storage_bytes(self):
        from files.models import FileItem
        total = FileItem.objects.filter(
            owner__company=self, is_deleted=False
        ).aggregate(total=models.Sum('size'))['total'] or 0
        return total


class Department(models.Model):
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='departments',
        verbose_name=_('entreprise')
    )
    name = models.CharField(_('nom'), max_length=150)
    description = models.TextField(_('description'), blank=True)
    manager = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='managed_departments', verbose_name=_('manager')
    )
    storage_quota_mb = models.PositiveIntegerField(_('quota (Mo)'), default=10240)  # 10 GB
    is_active = models.BooleanField(_('actif'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('département')
        verbose_name_plural = _('départements')
        unique_together = [['company', 'name']]
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.company.name})"


class Group(models.Model):
    """Groupe de travail au sein d'un département"""
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='groups',
        verbose_name=_('département')
    )
    name = models.CharField(_('nom'), max_length=100)
    description = models.TextField(blank=True)
    members = models.ManyToManyField(
        'accounts.User', related_name='work_groups', blank=True,
        verbose_name=_('membres')
    )
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True,
        related_name='created_groups'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('groupe')
        verbose_name_plural = _('groupes')
        unique_together = [['department', 'name']]

    def __str__(self):
        return f"{self.name} - {self.department.name}"
