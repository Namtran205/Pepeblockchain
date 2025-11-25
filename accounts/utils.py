import requests
import json
from django.conf import settings
from .crypto_utils import decrypt_key  # Dấu chấm (.) nghĩa là import từ cùng thư mục
# CẤU HÌNH API
HSCOIN_ENDPOINT = f"{settings.HSCOIN_API_BASE_URL}/smart-contract/execute" # Check lại endpoint chuẩn
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": settings.HSCOIN_API_KEY
}

def call_hscoin(caller, private_key, function_name, args):
    """Hàm wrapper để gửi request"""
    payload = {
        "caller": caller,
        "privateKey": private_key,  # Bắt buộc để server ký
        "contractAddress": settings.TOKEN_CONTRACT_ADDRESS,
        "value": 0,
        "inputData": {
            "function": function_name,
            "args": args
        }
    }
    try:
        response = requests.post(HSCOIN_ENDPOINT, json=payload, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Tùy response của HScoin mà lấy hash, ví dụ:
            tx_hash = data.get('transactionHash') or data.get('hash') or "Success"
            return True, tx_hash
        return False, f"API Error {response.status_code}: {response.text}"
    except Exception as e:
        return False, f"Connection Error: {str(e)}"

# 1. HÀM CHO ADMIN MINT (Dùng cho Rút tiền: Coins -> Token)
def admin_mint_tokens(receiver_address, amount):
    # Admin dùng Private Key của mình để tạo token cho user
    amount_wei = int(amount * (10 ** 18))
    return call_hscoin(
        caller=settings.ADMIN_WALLET_ADDRESS,
        private_key=settings.ADMIN_PRIVATE_KEY,
        function_name="mint",
        args=[receiver_address, amount_wei]
    )

# 2. HÀM CHO USER BURN (Dùng cho Nạp tiền: Token -> Coins)
def user_burn_tokens(user_address, encrypted_pk, amount):
    # User tự đốt token của mình
    user_pk = decrypt_key(encrypted_pk)
    amount_wei = int(amount * (10 ** 18))
    return call_hscoin(
        caller=user_address,
        private_key=user_pk,
        function_name="burn",
        args=[amount_wei]
    )

# 3. HÀM USER CHUYỂN TIỀN (Dùng cho P2P và Mua bán)
def user_transfer_tokens(sender_address, encrypted_pk, receiver_address, amount):
    # User chuyển token cho người khác (hoặc cho tác giả bài viết)
    user_pk = decrypt_key(encrypted_pk)
    amount_wei = int(amount * (10 ** 18))
    return call_hscoin(
        caller=sender_address,
        private_key=user_pk,
        function_name="transfer",
        args=[receiver_address, amount_wei]
    )


# ... (Các hàm call_hscoin, admin_mint_tokens... ở trên giữ nguyên) ...

# 4. HÀM LẤY SỐ DƯ (VIEW FUNCTION)
def hscoin_get_balance(user_address):
    """
    Gọi hàm 'balanceOf' để lấy số dư Token của user.
    Hàm này không tốn phí gas nên không cần private key xịn (có thể để trống hoặc dummy).
    """
    payload = {
        "caller": user_address,
        "contractAddress": settings.TOKEN_CONTRACT_ADDRESS,
        "value": 0,
        "inputData": {
            "function": "balanceOf",
            "args": [user_address]
        }
    }
    
    # Headers đã khai báo ở trên đầu file utils.py (HEADERS)
    # Nếu chưa có biến HEADERS hoặc HSCOIN_ENDPOINT trong scope này thì khai báo lại:
    api_url = f"{settings.HSCOIN_API_BASE_URL}/smart-contract/execute"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.HSCOIN_API_KEY
    }

    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            # API thường trả về kết quả trong 'decodedOutput' hoặc 'result'
            # Số dư trả về là dạng Wei (18 số 0), cần chia cho 10^18
            raw_balance = data.get('decodedOutput') or data.get('result')
            
            if raw_balance is None: 
                return 0.0
                
            return float(raw_balance) / (10 ** 18)
        else:
            print(f"Lỗi lấy số dư: {response.text}")
            return 0.0
    except Exception as e:
        print(f"Lỗi kết nối lấy số dư: {str(e)}")
        return 0.0
    


# accounts/utils.py
import requests
from django.conf import settings

# def hscoin_generate_new_wallet():
#     """
#     Gọi sang HScoin để tạo ví mới.
#     """
#     api_url = "https://hsc-w3oq.onrender.com/api/generate-wallet"
#     headers = {
#         "Content-Type": "application/json",
#         "x-api-key": settings.HSCOIN_API_KEY # Key được bảo vệ ở đây
#     }
    
#     try:
#         # API tạo ví thường là POST (hoặc GET tùy tài liệu HScoin)
#         # Giả sử là POST
#         response = requests.post(api_url, headers=headers, timeout=10)
        
#         if response.status_code == 200:
#             # Giả sử HScoin trả về: {"address": "0x...", "privateKey": "..."}
#             return True, response.json()
#         else:
#             return False, f"HScoin Error: {response.text}"
#     except Exception as e:
#         return False, str(e)



# accounts/utils.py
import requests # <--- QUAN TRỌNG
from django.conf import settings
from .crypto_utils import decrypt_key

# ... các hàm cũ ...

# === THÊM HÀM NÀY VÀO CUỐI FILE ===
def hscoin_create_new_wallet():
    """Gọi HScoin để tạo ví mới"""
    # Lưu ý: settings.HSCOIN_API_BASE_URL thường là ".../api"
    # Nên đường dẫn sẽ là ".../api/generate-wallet"
    url = f"{settings.HSCOIN_API_BASE_URL}/generate-wallet"
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.HSCOIN_API_KEY
    }
    
    try:
        # Gửi request POST rỗng để xin ví
        response = requests.post(url, json={}, headers=headers, timeout=15)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, f"Lỗi HScoin ({response.status_code}): {response.text}"
    except Exception as e:
        return False, f"Lỗi kết nối: {str(e)}"