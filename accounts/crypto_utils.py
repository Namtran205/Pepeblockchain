# accounts/crypto_utils.py
from cryptography.fernet import Fernet
from django.conf import settings
import base64

# --- CẤU HÌNH KHÓA MÃ HÓA ---
# Trong thực tế, bạn nên lưu key này vào biến môi trường (.env)
# Key này PHẢI là 32 url-safe base64-encoded bytes.
# Đây là key ví dụ tôi tạo sẵn cho bạn dùng luôn để test:
SECRET_KEY_ENCRYPT = b'2r5u8x/A?D(G+KbPeShVmYq3t6w9z$B&E)H@McQfTjWn' 
# (Lưu ý: Key trên là ví dụ, nếu muốn bảo mật cao hơn hãy tự generate key khác)

# Nếu độ dài key ví dụ trên không chuẩn base64, ta dùng code tự sinh key dưới đây để an toàn nhất:
# Cách an toàn: Tự sinh key nếu chưa có
# key = Fernet.generate_key() 
# Nhưng để code chạy ổn định mỗi lần restart server, ta fix cứng 1 key hợp lệ:
FIXED_KEY = b'8sTj6H-4k_5qL9oR2pZ1xV3mN7bA0cE8wY5dF2gH4jK=' 

try:
    cipher = Fernet(FIXED_KEY)
except Exception as e:
    # Nếu key lỗi, tạo key mới (chỉ dùng debug)
    print("Key lỗi, đang tạo key tạm:", e)
    cipher = Fernet(Fernet.generate_key())

def encrypt_key(raw_key):
    """Mã hóa Private Key trước khi lưu vào DB"""
    if not raw_key: return None
    # Fernet yêu cầu bytes, nên encode(), sau đó decode() về string để lưu DB
    return cipher.encrypt(raw_key.encode()).decode()

def decrypt_key(enc_key):
    """Giải mã Private Key từ DB ra để dùng"""
    if not enc_key: return None
    # Encode về bytes để giải mã, sau đó decode về string
    return cipher.decrypt(enc_key.encode()).decode()