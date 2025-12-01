# accounts/crypto_utils.py (PHIÊN BẢN ĐÃ SỬA)
from cryptography.fernet import Fernet
from django.conf import settings
# import base64 (Không cần thiết vì Fernet đã xử lý)

# --- KHỞI TẠO CIPHER SUITE AN TOÀN ---
# Lấy khóa từ settings (đã được đảm bảo load từ biến môi trường/mặc định an toàn)
# Khóa phải được .encode() về bytes trước khi truyền vào Fernet
try:
    _cipher_suite = Fernet(settings.FERNET_KEY.encode())
except Exception as e:
    # Nếu có lỗi (ví dụ: key không hợp lệ), in lỗi và dừng
    raise RuntimeError(f"Lỗi khởi tạo Fernet Cipher Suite: {e}. Vui lòng kiểm tra giá trị PEPE_CRYPTO_KEY")


def encrypt_key(raw_key: str) -> str | None:
    """Mã hóa Private Key trước khi lưu vào DB"""
    if not raw_key: return None
    # Fernet yêu cầu bytes, nên encode(), sau đó decode() về string để lưu DB
    return _cipher_suite.encrypt(raw_key.encode('utf-8')).decode('utf-8')


def decrypt_key(enc_key: str) -> str | None:
    """Giải mã Private Key từ DB ra để dùng"""
    if not enc_key: return None
    # Encode về bytes để giải mã, sau đó decode về string
    try:
        return _cipher_suite.decrypt(enc_key.encode('utf-8')).decode('utf-8')
    except Exception as e:
        # Nếu giải mã thất bại (dữ liệu hỏng/key sai), đảm bảo không trả về gì
        print(f"Lỗi khi giải mã Private Key: {e}")
        return None