from django.contrib import admin
from .models import Folder, FileItem, FileVersion, Permission


@admin.register(Folder)
class FolderAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'parent', 'department', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'department')
    search_fields = ('name',)


@admin.register(FileItem)
class FileItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'size', 'mime_type', 'version', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'mime_type')
    search_fields = ('name',)


@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = ('file_item', 'version_number', 'size', 'uploaded_by', 'created_at')


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('permission', 'user', 'group', 'folder', 'file_item', 'created_at')
    list_filter = ('permission',)
