from django.urls import path
from . import views

app_name = 'shares'

urlpatterns = [
    path('create/', views.create_share, name='create'),
    path('my/', views.my_shares, name='my_shares'),
    path('revoke/<int:share_id>/', views.revoke_share, name='revoke'),
    path('s/<str:token>/', views.public_share, name='public'),
]
