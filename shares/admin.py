from django.contrib import admin
from .models import ShareLink, ShareAccessLog


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = ('token', 'file_item', 'folder', 'created_by', 'is_active', 'download_count', 'expires_at')
    list_filter = ('is_active',)
    readonly_fields = ('token', 'download_count', 'last_accessed')


@admin.register(ShareAccessLog)
class ShareAccessLogAdmin(admin.ModelAdmin):
    list_display = ('share_link', 'ip_address', 'accessed_at', 'success')
    readonly_fields = ('share_link', 'ip_address', 'user_agent', 'accessed_at', 'success')
