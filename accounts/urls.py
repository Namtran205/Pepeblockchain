from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('',views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('update-avatar/', views.update_avatar, name='update_avatar'),
    path('api/link-wallet/', views.api_link_wallet, name='api_link_wallet'),
    
    # API Hủy liên kết ví (Cần cho nút Hủy trong HTML)
    path('api/unlink-wallet/', views.unlink_wallet, name='unlink_wallet'),

    # API Nạp / Rút
    path('api/withdraw/', views.api_withdraw, name='api_withdraw'),
    path('api/deposit/', views.api_deposit, name='api_deposit'),
    
    # API Lấy số dư Token (Cho Javascript gọi cập nhật giao diện)
    path('api/get-balance/', views.api_get_balance, name='api_get_balance'),
    
    # API Mua bài test (Cho trang danh sách bài test)
    path('api/buy-content/', views.api_buy_content, name='api_buy_content'),

    ]