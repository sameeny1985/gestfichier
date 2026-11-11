from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'role', 'company', 'department', 'is_active')
    list_filter = ('role', 'is_active', 'company', 'department')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Informations personnelles'), {'fields': ('first_name', 'last_name', 'phone', 'avatar')}),
        (_('Rôle et organisation'), {'fields': ('role', 'company', 'department', 'storage_quota_mb')}),
        (_('Permissions'), {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        (_('Sécurité'), {'fields': ('two_factor_enabled', 'failed_login_attempts')}),
        (_('Dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )
