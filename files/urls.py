from django.urls import path
from . import views

app_name = 'files'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('browser/', views.file_browser, name='browser'),
    path('browser/<int:folder_id>/', views.file_browser, name='browser_folder'),
    path('upload/', views.upload_file, name='upload'),
    path('folder/create/', views.create_folder, name='create_folder'),
    path('download/<int:file_id>/', views.download_file, name='download'),
    path('delete/', views.delete_item, name='delete'),
    path('trash/', views.trash, name='trash'),
    path('restore/', views.restore_item, name='restore'),
    path('shared/', views.shared_files, name='shared'),
    path('rename/', views.rename_item, name='rename'),
]
