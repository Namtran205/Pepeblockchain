import os
import hashlib
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.files.storage import default_storage
from django.db import connection
from django.http import Http404
from django.shortcuts import render, redirect
from web3 import Web3
from .crypto_utils import encrypt_key
from django.contrib.auth.decorators import login_required
from . import sql
from .models import User
from django.db import transaction


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def index(request): 
    # Kiểm tra session
    if not request.session.get('user_id'):
        messages.warning(request, 'Vui lòng đăng nhập để tiếp tục')
        return redirect('accounts:login')
    
    user_id = request.session.get('user_id')
    user_type = request.session.get('user_type')

    context = {
        'is_authenticated': True,
        'user_type': user_type,
        'user_id': user_id,
        'username': request.session.get('username'),
        'email': request.session.get('email', ''),
        'avatar_path': None,
        'full_name': '',
        'all_major': [],
        'all_departments': [],
        'all_subjects': [],
        'current_subject_ids': set(),
        'subjects_taught_names': [],
        'recent_activities': [],  # THÊM: Danh sách hoạt động gần đây
        'stats': {'uploads': 0, 'tests': 0}
    }

    # --- XỬ LÝ POST (Cập nhật thông tin) ---
    if request.method == 'POST':
        full_name = request.POST.get('full_name','').strip()
        name_parts = full_name.split(' ', 1) if full_name else ['', '']
        first_name = name_parts[0] if len(name_parts) > 0 else ''
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        try:
            sql.update_user_name(first_name, last_name, user_id)

            if user_type == 'student':
                major_id = request.POST.get('major_id') or None
                student_code = request.POST.get('student_code').strip() or None
                enrollment_year = request.POST.get('enrollment_year') or None
                sql.update_student(user_id, major_id, enrollment_year, student_code)

            elif user_type == 'teacher':
                title = request.POST.get('title', '').strip()
                degree = request.POST.get('degree', '').strip()
                department_id = request.POST.get('department') or None
                teacher_code = request.POST.get('teacher_code').strip() or None
                sql.update_teacher(user_id, title, teacher_code, degree, department_id)

            messages.success(request, 'Cập nhật thông tin thành công!')
            return redirect('accounts:index')

        except Exception as e:
            messages.error(request, f'Cập nhật thất bại: {e}')

    # --- XỬ LÝ GET (Hiển thị thông tin) ---
    try:
        # Lấy thông tin chung
        user_data = sql.one_user(user_id=user_id)
        if not user_data:
            raise Http404("Không tìm thấy người dùng.")
            
        context['username'] = user_data['username']
        context['email'] = user_data['email']
        context['first_name'] = user_data['first_name'] or ''
        context['last_name'] = user_data['last_name'] or ''
        context['full_name'] = f"{context['first_name']} {context['last_name']}".strip()
        context['avatar_path'] = f"{user_data['avatar_path']}" if user_data['avatar_path'] else None

        if user_type == 'student':
            student_data = sql.one_student(user_id)
            if student_data:
                context['current_major_id'] = student_data['major_id']
                context['major_name'] = student_data['major_name']
                context['enrollment_year'] = student_data['enrollment_year']
                context['student_code'] = student_data['student_code']

            # Lấy danh sách majors
            context['all_major'] = sql.all_major()
            
            # THÊM: Lấy thống kê thực tế cho sinh viên
            # Số bài kiểm tra đã làm
            context['stats']['tests'] = sql.user_submission_count(user_id)
            
            # Số bài đã đăng
            context['stats']['uploads'] = sql.user_post_count(user_id)

            # Lấy hoạt động gần đây thực tế
            recent_activities = []
            for test in sql.user_recent_submissions(user_id, 3):
                recent_activities.append({
                    'icon': 'bi-pencil-square text-success',
                    'text': f'Hoàn thành bài kiểm tra "{test['title']}"',
                    'time': test['created_at']
                })
            
            # Lấy tài liệu tải lên gần đây
            for post in sql.user_recent_posts(user_id, 3):
                recent_activities.append({
                    'icon': 'bi-cloud-upload text-primary',
                    'text': f'Tải lên Bài đăng "{post['title']}"',
                    'time': post['created_at']
                })
                
            # Sắp xếp theo thời gian mới nhất
            recent_activities.sort(key=lambda x: x['time'], reverse=True)
            context['recent_activities'] = recent_activities[:3]  # Lấy 3 hoạt động gần nhất

        elif user_type == 'teacher':
            # Lấy dữ liệu GIẢNG VIÊN
            teacher_data = sql.one_teacher(user_id)
            if teacher_data:
                context['title'] = teacher_data['title']
                context['current_department_id'] = teacher_data['department_id']
                context['department_name'] = teacher_data['department_name']
                context['degree'] = teacher_data['degree']
                context['teacher_code'] = teacher_data['teacher_code']
            
            # Lấy danh sách departments
            context['all_departments'] = sql.all_department()
            
            # THÊM: Lấy thống kê thực tế cho giảng viên
            # Số bài kiểm tra đã tạo
            context['stats']['tests'] = sql.user_test_count(user_id)
            
            # Số tài liệu đã tải lên
            context['stats']['uploads'] = sql.user_post_count(user_id)

            # THÊM: Lấy hoạt động gần đây thực tế
            recent_activities = []
            
            # Lấy bài kiểm tra tạo gần đây
            for test in sql.user_recent_tests(user_id, 3):
                recent_activities.append({
                    'icon': 'bi-plus-circle text-success',
                    'text': f'Tạo bài kiểm tra "{test['title']}"',
                    'time': test['created_at']
                })
            
            for post in sql.user_recent_posts(user_id, 3):
                recent_activities.append({
                    'icon': 'bi-cloud-upload text-primary',
                    'text': f'Tải lên Bài đăng "{post['title']}"',
                    'time': post['created_at']
                })
            
            # Sắp xếp theo thời gian mới nhất
            recent_activities.sort(key=lambda x: x['time'], reverse=True)
            context['recent_activities'] = recent_activities[:3]  # Lấy 3 hoạt động gần nhất
            
    except Exception as e:
        messages.error(request, f"Lỗi khi tải dữ liệu trang: {e}")

    return render(request, 'accounts/index.html', context)


def register_view(request):
    # --- GET: Lưu ref code từ URL ---
    ref_code_username = request.GET.get('ref')
    if ref_code_username:
        try:
            from .models import User as UserModel
            if UserModel.objects.filter(username=ref_code_username).exists():
                request.session['ref_code_username'] = ref_code_username
            else:
                messages.warning(request, "Mã giới thiệu không hợp lệ.")
        except Exception:
            pass

    # --- GET: Hiển thị form ---
    if request.method != 'POST':
        return render(request, 'accounts/register.html', {
            'ref_code_username': request.session.get('ref_code_username')
        })

    # --- POST: Lấy dữ liệu ---
    username = request.POST.get('username')
    email = request.POST.get('email')
    password = request.POST.get('password')
    password_confirm = request.POST.get('password_confirm')
    first_name = request.POST.get('first_name') or None
    last_name = request.POST.get('last_name') or None
    user_type = request.POST.get('user_type')

    # --- Validation cơ bản ---
    if password != password_confirm:
        messages.error(request, 'Mật khẩu không khớp')
        return render(request, 'accounts/register.html')

    if len(password) < 6:
        messages.error(request, 'Mật khẩu phải có ít nhất 6 ký tự')
        return render(request, 'accounts/register.html')

    hashed_password = hash_password(password)

    try:
        # Kiểm tra trùng username hoặc email
        if sql.one_user(username=username, email=email):
            messages.error(request, 'Tên đăng nhập hoặc email đã tồn tại')
            return render(request, 'accounts/register.html')

        # --- Tạo user ---
        new_user_id = sql.insert_user(username, email, hashed_password, first_name, last_name, user_type)

        # -----------------------------------------------------
        #      XỬ LÝ GIỚI THIỆU THEO HÀM MẪU BẠN MUỐN
        # -----------------------------------------------------
        referrer_username = request.session.get('ref_code_username')
        referred_user = User.objects.get(pk=new_user_id)


        if referrer_username:
            try:
                from .models import Referral, User as UserModel
                referrer_user = User.objects.filter(username=referrer_username).first()
                if not referrer_user:
                    raise Exception("Referrer user not found")


                if referrer_user:
                    with transaction.atomic():
                        # tạo record referral
                        referral = Referral.objects.create(referrer=referrer_user, referred=referred_user)

                        # thưởng coin
                        referred_user.coins = (referred_user.coins or 0) + 50
                        referred_user.save()

                        referrer_user.coins = (referrer_user.coins or 0) + 50
                        referrer_user.save()

                        referral.rewarded_referred = True
                        referral.rewarded_referrer = True
                        referral.save()

                    messages.success(request, f"Đăng ký thành công! Bạn và ({referrer_username}) đã nhận 50 coin.")
                else:
                    messages.warning(request, "Mã giới thiệu không hợp lệ.")

                # xóa khỏi session
                if 'ref_code_username' in request.session:
                    del request.session['ref_code_username']

            except Exception as e:
                messages.warning(request, "Đăng ký thành công nhưng có lỗi khi xử lý giới thiệu.")

        else:
            messages.success(request, 'Đăng ký thành công! Vui lòng đăng nhập.')

        # Redirect về login
        return redirect('accounts:login')

    except Exception as e:
        messages.error(request, f'Lỗi: {str(e)}')
        return render(request, 'accounts/register.html')
 


def login_view(request):
    if request.method != 'POST':
        return render(request, 'accounts/login.html')

    username = request.POST.get('username')
    password = request.POST.get('password')
    user_data = sql.one_user(username=username)
        
    if not user_data or not verify_password(password, user_data['password']):
        messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng')
        return render(request, 'accounts/login.html')
    
    # Lưu thông tin user vào session
    request.session['is_authenticated'] = request.session.get('user_id') is not None
    request.session['user_id']   = user_data['id']
    request.session['username']  = user_data['username']
    request.session['email']     = user_data['email']
    request.session['user_type'] = 'student' if sql.one_student(user_data['id']) else 'teacher'

    # Referral reward: if this user was referred and not yet rewarded, give coins
    try:
        from .models import Referral, User as UserModel
        referred_user = UserModel.objects.get(pk=user_data['id'])
        referral = Referral.objects.filter(referred=referred_user, rewarded_referred=False).first()
        if referral:
            # award new user 10 coins
            referred_user.coins = (referred_user.coins or 0) + 10
            referred_user.save()
            # award referrer 50 coins
            referrer = referral.referrer
            referrer.coins = (referrer.coins or 0) + 50
            referrer.save()
            # mark rewarded
            referral.rewarded_referred = True
            referral.rewarded_referrer = True
            referral.save()
            messages.success(request, 'Bạn và người giới thiệu đã nhận thưởng từ chương trình giới thiệu!')
    except Exception:
        pass
    messages.success(request, f'Xin chào {request.session['username']}!')
    return redirect('home:index')


def logout_view(request):
    request.session.flush()
    messages.success(request, 'Đã đăng xuất!')
    return redirect('home:index')


def update_avatar(request):
    """Xử lý upload avatar cho student"""
    if not request.session.get('user_id'):
        messages.error(request, 'Vui lòng đăng nhập')
        return redirect('accounts:login')
    
    if request.method != 'POST':        
        return redirect('accounts:index_student')
    user_id = request.session.get('user_id')
    avatar_file = request.FILES.get('avatar')
    
    if not avatar_file:
        messages.error(request, 'Vui lòng chọn ảnh')
        return redirect('accounts:index_student')
    
    # Validate file
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']
    file_ext = Path(avatar_file.name).suffix.lower()
    
    if file_ext not in allowed_extensions:
        messages.error(request, 'Chỉ chấp nhận file ảnh (jpg, jpeg, png, gif)')
        return redirect('accounts:index_student')
    
    if avatar_file.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        messages.error(request, f'Kích thước file không được vượt quá {settings.FILE_UPLOAD_MAX_MEMORY_SIZE // (1024 ** 2)}MB')
        return redirect('accounts:index_student')
    
    try:
        # Tạo tên file unique
        file_name = f"{user_id}_{hash(avatar_file.name)}{file_ext}"
        file_path = Path('avatars') / file_name

        # Xóa avatar cũ nếu có
        user_data = sql.one_user(user_id=user_id)
        if user_data and user_data['avatar_path']:        
            old_path = settings.MEDIA_ROOT / user_data['avatar_path']
            if old_path.exists():
                try:
                    os.remove(old_path)
                except:
                    pass
        
        # Lưu file mới
        full_path = default_storage.save(str(file_path), avatar_file)
        sql.update_user_avatar(settings.MEDIA_URL + full_path, user_id)
        
        messages.success(request, 'Cập nhật ảnh đại diện thành công!')
        
    except Exception as e:
        messages.error(request, f'Lỗi khi tải ảnh: {str(e)}')

    return redirect('accounts:index')


from django.shortcuts import get_object_or_404
from django.db import connection, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .utils import admin_mint_tokens, user_burn_tokens, user_transfer_tokens

# Helper lấy ví user
def get_user_wallet(user_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT wallet_address, encrypted_private_key FROM students WHERE id = %s", [user_id])
        return cursor.fetchone()

# ======================================================
# 1. RÚT COINS -> TOKENS (User đổi điểm thành Token)
# ======================================================
@login_required
@require_POST
def api_withdraw(request):
    user_id = request.session.get('user_id')
    amount = float(json.loads(request.body).get('amount'))

    row = get_user_wallet(user_id)
    if not row: return JsonResponse({'success': False, 'message': 'Chưa liên kết ví'})
    user_address = row[0]

    with connection.cursor() as cursor:
        # 1. Trừ Coins trong DB trước (để tránh spam)
        cursor.execute("SELECT coins FROM students WHERE id = %s", [user_id])
        current_coins = cursor.fetchone()[0]
        
        if current_coins < amount:
            return JsonResponse({'success': False, 'message': 'Không đủ Coins'})

        cursor.execute("UPDATE students SET coins = coins - %s WHERE id = %s", [amount, user_id])

        # 2. Gọi Admin Mint Token trả cho user
        success, result = admin_mint_tokens(user_address, amount)

        if success:
            return JsonResponse({'success': True, 'message': f'Rút thành công! Hash: {result}'})
        else:
            # 3. Nếu lỗi blockchain -> Hoàn tiền lại DB (Rollback)
            cursor.execute("UPDATE students SET coins = coins + %s WHERE id = %s", [amount, user_id])
            return JsonResponse({'success': False, 'message': f'Lỗi Blockchain: {result}'})

# ======================================================
# 2. NẠP TOKENS -> COINS (User đốt Token để lấy điểm)
# ======================================================
@login_required
@require_POST
def api_deposit(request):
    user_id = request.session.get('user_id')
    amount = float(json.loads(request.body).get('amount'))

    row = get_user_wallet(user_id)
    if not row: return JsonResponse({'success': False, 'message': 'Chưa liên kết ví'})
    user_address, encrypted_pk = row

    # 1. Gọi User Burn Token trên Blockchain
    success, result = user_burn_tokens(user_address, encrypted_pk, amount)

    if success:
        # 2. Nếu thành công -> Cộng Coins vào DB
        with connection.cursor() as cursor:
            cursor.execute("UPDATE students SET coins = coins + %s WHERE id = %s", [amount, user_id])
        return JsonResponse({'success': True, 'message': f'Nạp thành công! Hash: {result}'})
    else:
        return JsonResponse({'success': False, 'message': f'Lỗi Blockchain: {result}'})

# ======================================================
# 3. CHUYỂN TIỀN P2P (User A -> User B)
# ======================================================
@login_required
@require_POST
def api_transfer_p2p(request):
    sender_id = request.session.get('user_id')
    data = json.loads(request.body)
    receiver_address = data.get('receiver_address')
    amount = float(data.get('amount'))

    sender_row = get_user_wallet(sender_id)
    if not sender_row: return JsonResponse({'success': False, 'message': 'Chưa liên kết ví'})
    sender_addr, sender_enc_pk = sender_row

    # Gọi hàm Transfer
    success, result = user_transfer_tokens(sender_addr, sender_enc_pk, receiver_address, amount)

    if success:
        return JsonResponse({'success': True, 'message': f'Chuyển thành công! Hash: {result}'})
    else:
        return JsonResponse({'success': False, 'message': result})

# ======================================================
# 4. MUA BÀI TEST / TÀI LIỆU (User -> Creator)
# ======================================================
@login_required
@require_POST
def api_buy_content(request):
    buyer_id = request.session.get('user_id')
    data = json.loads(request.body)
    item_id = data.get('id')
    item_type = data.get('type') # 'test' hoặc 'doc'

    # 1. Lấy thông tin người mua
    buyer_row = get_user_wallet(buyer_id)
    if not buyer_row: return JsonResponse({'success': False, 'message': 'Bạn chưa liên kết ví'})
    buyer_addr, buyer_enc_pk = buyer_row

    with connection.cursor() as cursor:
        # 2. Lấy giá tiền và ví tác giả từ DB
        if item_type == 'test':
            cursor.execute("""
                SELECT t.price, s.wallet_address, t.owner_id 
                FROM tests t JOIN students s ON t.owner_id = s.id 
                WHERE t.id = %s
            """, [item_id])
        else: # Tài liệu
            cursor.execute("""
                SELECT d.price, s.wallet_address, d.owner_id 
                FROM documents d JOIN students s ON d.owner_id = s.id 
                WHERE d.id = %s
            """, [item_id])
        
        item_info = cursor.fetchone()
        if not item_info: return JsonResponse({'success': False, 'message': 'Nội dung không tồn tại'})

        price, creator_address, owner_id = item_info

        # Check logic cơ bản
        if buyer_id == owner_id:
            return JsonResponse({'success': False, 'message': 'Không thể tự mua bài của mình'})
        if not creator_address:
            return JsonResponse({'success': False, 'message': 'Tác giả chưa có ví để nhận tiền'})

        # 3. Thực hiện giao dịch Blockchain: Buyer -> Creator
        success, result = user_transfer_tokens(buyer_addr, buyer_enc_pk, creator_address, price)

        if success:
            # 4. Mở khóa nội dung (Lưu vào bảng đã mua)
            table = "purchased_tests" if item_type == 'test' else "purchased_docs"
            col_id = "test_id" if item_type == 'test' else "doc_id"
            
            cursor.execute(f"INSERT INTO {table} (user_id, {col_id}) VALUES (%s, %s)", [buyer_id, item_id])
            
            return JsonResponse({'success': True, 'message': 'Mua thành công! Đã mở khóa.'})
        else:
             return JsonResponse({'success': False, 'message': f'Thanh toán thất bại: {result}'})
        


# accounts/views.py

# ... (Các hàm api_link_wallet, api_withdraw... đã có ở trên) ...
# ======================================================
# 5. LIÊN KẾT VÍ (Lưu Address + Private Key đã mã hóa)
# ======================================================

# accounts/views.py
import json
import traceback # <--- QUAN TRỌNG: Thêm dòng này để soi lỗi
from django.shortcuts import render, redirect
from django.db import connection
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from web3 import Web3 
from .crypto_utils import encrypt_key

@require_POST
def api_link_wallet(request):
    if not request.session.get('user_id'):
        return JsonResponse({'success': False, 'message': 'Bạn chưa đăng nhập.'})
    print("--- BẮT ĐẦU XỬ LÝ LIÊN KẾT VÍ ---") # Debug log 1
    try:
        data = json.loads(request.body)
        private_key = data.get('private_key', '').strip()
        
        if not private_key:
            return JsonResponse({'success': False, 'message': 'Thiếu Private Key'})

        # 1. Suy ra địa chỉ
        print(f"Đang kiểm tra Private Key: {private_key[:5]}...") # Debug log 2
        try:
            w3_temp = Web3()
            account = w3_temp.eth.account.from_key(private_key)
            real_address = account.address
            print(f"Địa chỉ suy ra: {real_address}") # Debug log 3
        except Exception as e:
             print(f"Lỗi Web3: {e}")
             return JsonResponse({'success': False, 'message': 'Private Key sai định dạng.'})

        # 2. Mã hóa
        encrypted_pk = encrypt_key(private_key)
        print("Mã hóa thành công.") # Debug log 4
        
        # 3. Lưu vào DB
        user_id = request.session.get('user_id')
        print(f"Đang lưu vào DB cho user_id: {user_id}") # Debug log 5
        
        with connection.cursor() as cursor:
            # --- ĐÂY LÀ CHỖ HAY LỖI NHẤT (DO THIẾU CỘT TRONG DB) ---
            cursor.execute(
                "UPDATE students SET wallet_address = %s, encrypted_private_key = %s WHERE id = %s",
                [real_address, encrypted_pk, user_id]
            )
            
        return JsonResponse({
            'success': True, 
            'message': f'Liên kết thành công! Ví: {real_address}'
        })

    except Exception as e:
        # IN LỖI CHI TIẾT RA TERMINAL
        print("❌ LỖI NGHIÊM TRỌNG (SERVER CRASH):")
        traceback.print_exc() # <--- Dòng này sẽ in toàn bộ lỗi ra màn hình đen
        return JsonResponse({'success': False, 'message': f'Lỗi Server: {str(e)}'})



from django.views.decorators.http import require_POST
# accounts/views.py

# 1. API HỦY LIÊN KẾT VÍ
@login_required
@require_POST
def unlink_wallet(request):
    user_id = request.session.get('user_id')
    with connection.cursor() as cursor:
        # Xóa private key và address khỏi DB
        cursor.execute("UPDATE students SET wallet_address = NULL, encrypted_private_key = NULL WHERE id = %s", [user_id])
    return redirect('wallet') # Load lại trang ví

# 2. API LẤY SỐ DƯ TOKEN (Cho Frontend cập nhật)
@login_required
def api_get_balance(request):
    user_id = request.session.get('user_id')
    with connection.cursor() as cursor:
        cursor.execute("SELECT wallet_address FROM students WHERE id = %s", [user_id])
        row = cursor.fetchone()
    
    if row and row[0]:
        # Gọi hàm utils để check blockchain
        # Lưu ý: Bạn cần chắc chắn hàm hscoin_get_balance đã có trong utils.py
        # Nếu chưa có hàm hscoin_get_balance, bạn có thể trả về 0 tạm thời
        try:
             # balance = hscoin_get_balance(row[0]) 
             balance = 0 # Tạm thời để 0 nếu chưa viết hàm check balance trong utils
             return JsonResponse({'success': True, 'balance': balance})
        except:
             return JsonResponse({'success': False, 'balance': 0})
    
    return JsonResponse({'success': False, 'balance': 0})
