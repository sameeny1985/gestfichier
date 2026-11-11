from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('L\'adresse e-mail est obligatoire'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.TECH_ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        TECH_ADMIN = 'tech_admin', _('Administrateur technique')
        COMPANY_ADMIN = 'company_admin', _('Administrateur d\'entreprise')
        MANAGER = 'manager', _('Manager de département')
        EMPLOYEE = 'employee', _('Employé')

    username = None  # Use email as identifier
    email = models.EmailField(_('adresse e-mail'), unique=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        verbose_name=_('rôle')
    )
    phone = models.CharField(_('téléphone'), max_length=20, blank=True)
    avatar = models.ImageField(_('avatar'), upload_to='avatars/', blank=True, null=True)
    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        verbose_name=_('entreprise')
    )
    department = models.ForeignKey(
        'companies.Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name=_('département')
    )
    storage_quota_mb = models.PositiveIntegerField(
        _('quota de stockage (Mo)'),
        default=1024,  # 1 GB default
        help_text=_('Quota de stockage personnel en mégaoctets')
    )
    is_active = models.BooleanField(_('actif'), default=True)
    two_factor_enabled = models.BooleanField(_('2FA activé'), default=False)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = _('utilisateur')
        verbose_name_plural = _('utilisateurs')
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>" if self.get_full_name() else self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def used_storage_bytes(self):
        from files.models import FileItem
        total = FileItem.objects.filter(owner=self, is_deleted=False).aggregate(
            total=models.Sum('size')
        )['total'] or 0
        return total

    @property
    def used_storage_mb(self):
        return round(self.used_storage_bytes / (1024 * 1024), 2)

    @property
    def storage_usage_percent(self):
        if self.storage_quota_mb == 0:
            return 0
        return min(100, round((self.used_storage_mb / self.storage_quota_mb) * 100, 1))

    def has_role(self, *roles):
        return self.role in roles or self.is_superuser
