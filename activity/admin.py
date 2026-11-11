from django.contrib import admin
from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'target_name', 'ip_address', 'created_at')
    list_filter = ('action',)
    search_fields = ('user__email', 'target_name')
    readonly_fields = ('user', 'action', 'target_type', 'target_id', 'target_name', 'details', 'ip_address', 'created_at')
