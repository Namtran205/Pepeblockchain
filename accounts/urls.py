from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # --- Các View cơ bản (Profile, Auth) ---
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('update-avatar/', views.update_avatar, name='update_avatar'),

    # --- Các API Ví & Blockchain ---
    
    # 1. Liên kết ví (Mới - Nhập tay)
    path('api/link-wallet/', views.api_link_wallet, name='api_link_wallet'),
    
    # 2. Hủy liên kết ví
    path('api/unlink-wallet/', views.unlink_wallet, name='unlink_wallet'),

    # 3. Lấy số dư Token (cho Frontend cập nhật)
    path('api/get-balance/', views.api_get_balance, name='api_get_balance'),

    # 4. Nạp / Rút tiền
    path('api/deposit/', views.api_deposit, name='api_deposit'),
    path('api/withdraw/', views.api_withdraw, name='api_withdraw'),

    # 5. Chuyển tiền P2P
    path('api/transfer/', views.api_transfer_p2p, name='api_transfer_p2p'),
    
    # 6. Mua nội dung (Bài test / Tài liệu)
    path('api/buy-content/', views.api_buy_content, name='api_buy_content'),

    # (Optional) Nếu bạn vẫn giữ view cũ để backup thì có thể để lại, 
    # nhưng đảm bảo hàm 'api_auto_create_wallet' tồn tại trong views.py
    # path('api/auto-create-wallet/', views.api_auto_create_wallet, name='api_auto_create_wallet'),
]