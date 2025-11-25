from django.urls import path

from . import views

app_name = 'wallet'

urlpatterns = [
    path('', views.wallet, name='index'),
    path('referral/', views.referral, name='referral'),
    path('checkin/', views.checkin_view, name='checkin'),
]