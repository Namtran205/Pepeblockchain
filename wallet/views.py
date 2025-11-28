from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from datetime import date

from accounts.models import User


# import Referral lazily in functions to avoid cyclic import on startup


def wallet(request):
    """Ví điểm - dùng session thay vì Django auth (ORM)"""
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập để xem ví')
        return redirect('accounts:login')

    username = request.session.get('username', '')
    user_id = request.session.get('user_id')

    # Lấy thông tin user từ DB để hiển thị coin (ORM)
    user_coins = 0
    try:
        user = User.objects.get(pk=user_id)
        user_coins = user.coins or 0
    except User.DoesNotExist:
        user_coins = 0

    # Lấy thông tin ví (student) để hiển thị wallet address nếu đã liên kết
    has_wallet = False
    wallet_address = None
    try:
        from accounts.models import Student
        student = Student.objects.filter(pk=user_id).first()
        if student and getattr(student, 'wallet_address', None):
            has_wallet = True
            wallet_address = student.wallet_address
    except Exception:
        # Nếu model không tồn tại hoặc lỗi, để mặc định là chưa có ví
        has_wallet = False
        wallet_address = None
    
    # Tạo referral link
    referral_link = "#"
    try:
        scheme = request.scheme
        domain = request.get_host()
        register_url = reverse('accounts:register')
        referral_link = f"{scheme}://{domain}{register_url}?ref={username}"
    except Exception as e:
        print(f"Lỗi tạo link giới thiệu: {e}")
    
    # Lấy lịch sử giao dịch (nếu có)
    transaction_history = []
    try:
        from accounts.utils import read_user_txs
        transaction_history = read_user_txs(user_id, limit=50)
    except Exception:
        transaction_history = []
    
    context = {
        'username': username,
        'user_coins': user_coins,
        'referral_link': referral_link,
        'transactions': transaction_history,
        'is_authenticated': True,
        'has_wallet': has_wallet,
        'wallet_address': wallet_address,
    }
    return render(request, 'wallet/index.html', context)


def referral(request):
    """Trang giới thiệu - dùng session"""
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập')
        return redirect('accounts:login')
    
    username = request.session.get('username', '')
    
    # Tạo link giới thiệu
    referral_link = "#"
    try:
        scheme = request.scheme
        domain = request.get_host()
        register_url = reverse('accounts:register')
        referral_link = f"{scheme}://{domain}{register_url}?ref={username}"
    except Exception as e:
        print(f"Lỗi tạo link giới thiệu: {e}")
    
    # Lấy dữ liệu giới thiệu từ DB
    try:
        from accounts.models import Referral
        current_user = User.objects.get(pk=request.session.get('user_id'))
        # Chỉ tính những lượt giới thiệu đã được đánh dấu "rewarded_referrer"
        successful_referrals = Referral.objects.filter(referrer=current_user, rewarded_referrer=True).select_related('referred').order_by('-created_at')
        referrals_made_count = successful_referrals.count()
        # theo policy hiện tại: referrer nhận 50 coin mỗi lượt thành công
        coins_earned = referrals_made_count * 50
        # Mảng kết quả cho template: username + ngày giới thiệu
        recent_referrals_list = [
            {'username': r.referred.username, 'date_joined': r.created_at}
            for r in successful_referrals[:10]
        ]
    except Exception:
        referrals_made_count = 0
        coins_earned = 0
        recent_referrals_list = []
    
    context = {
        'username': username,
        'referral_link': referral_link,
        'referrals_made_count': referrals_made_count,
        'coins_earned_from_referrals': coins_earned,
        'recent_referrals_list': recent_referrals_list,
        'is_authenticated': True,
    }
    return render(request, 'wallet/referral.html', context)


def checkin_view(request):
    """Điểm danh hằng ngày - nhận coin"""
    if request.method != 'POST':
        return redirect('home:index')
    
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập để điểm danh')
        return redirect('accounts:login')
    
    user_id = request.session.get('user_id')
    COIN_REWARD = 5
    today = date.today()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        messages.error(request, 'Tài khoản không tồn tại')
        return redirect('home:index')

    last_checkin = user.last_checkin
    if last_checkin == today:
        messages.error(request, 'Bạn đã điểm danh hôm nay rồi!')
    else:
        user.coins = (user.coins or 0) + COIN_REWARD
        user.last_checkin = today
        user.save()
        messages.success(request, f'Bạn đã điểm danh thành công và nhận được {COIN_REWARD} coin!')

    return redirect('home:index')