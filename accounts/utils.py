import requests
import json
import re
import logging
from django.conf import settings
from .crypto_utils import decrypt_key  # Dấu chấm (.) nghĩa là import từ cùng thư mục

logger = logging.getLogger(__name__)
# CẤU HÌNH API
HSCOIN_ENDPOINT = f"{settings.HSCOIN_API_BASE_URL}/api/contracts/0x09cd83a79934e0ceefef4fd8d5bb901edaa9af7f/execute" # Check lại endpoint chuẩn
print("HSCOIN_ENDPOINT =", HSCOIN_ENDPOINT)
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
        # Debug: log request we send to HScoin (avoid logging private key in prod)
        redacted = dict(payload)
        if 'privateKey' in redacted:
            redacted['privateKey'] = '<redacted>'
        logger.debug(f"Calling HScoin POST {HSCOIN_ENDPOINT} payload={redacted} headers={HEADERS}")
        response = requests.post(HSCOIN_ENDPOINT, json=payload, headers=HEADERS, timeout=15)
        # If HScoin responds 405, retry with a trailing slash (many servers differ)
        if response.status_code == 405:
            try_url = HSCOIN_ENDPOINT.rstrip('/') + '/'
            logger.warning(f"HScoin returned 405 for POST {HSCOIN_ENDPOINT}, retrying POST {try_url}")
            response = requests.post(try_url, json=payload, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Tùy response của HScoin mà lấy hash, ví dụ:
            tx_hash = data.get('transactionHash') or data.get('hash') or "Success"
            return True, tx_hash
        # Log non-200 for debugging
        logger.warning(f"HScoin returned status {response.status_code} for call: {response.text[:800]}")
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

        if response.status_code != 200:
            # Trả về chi tiết lỗi để dễ debug
            msg = f"Lỗi HScoin ({response.status_code}): {response.text}"
            print(msg)
            return False, msg

        # Parse JSON trả về
        try:
            data = response.json()
        except Exception as e:
            txt = response.text or ''
            msg = f"HScoin trả về không phải JSON: {str(e)} -- {txt[:200]}"
            print(msg)
            return False, msg

        # Cố gắng tìm address/privateKey trong nhiều vị trí khả dĩ.
        # Chiến lược:
        # 1) Kiểm tra các key phổ biến (address, walletAddress, privateKey, private_key)
        # 2) Nếu không tìm thấy, quét toàn bộ JSON và trích xuất chuỗi phù hợp với mẫu ETH address (0x...40hex)
        #    và private key (64 hex chars).
        def _get(d, *keys):
            for k in keys:
                if isinstance(d, dict) and k in d:
                    return d.get(k)
            return None

        address = _get(data, 'address', 'walletAddress', 'wallet_address', 'addS', 'adds', 'add') or (data.get('result') or {}).get('address') or (data.get('data') or {}).get('address')
        pk = _get(data, 'privateKey', 'private_key', 'privKey', 'private') or (data.get('result') or {}).get('privateKey') or (data.get('data') or {}).get('privateKey')
        print(address, pk)
        # Nếu chưa có address hoặc pk, scan toàn bộ JSON text để tìm các pattern phù hợp
        def _collect_strings(obj, acc):
            if isinstance(obj, str):
                acc.append(obj)
            elif isinstance(obj, dict):
                for v in obj.values():
                    _collect_strings(v, acc)
            elif isinstance(obj, list):
                for item in obj:
                    _collect_strings(item, acc)

        if (not address) or (not pk):
            all_strings = []
            _collect_strings(data, all_strings)
            # tìm ETH address (0x + 40 hex)
            eth_re = re.compile(r'0x[0-9a-fA-F]{40}')
            found_eth = None
            for s in all_strings:
                m = eth_re.search(s)
                if m:
                    found_eth = m.group(0).lower()
                    break
            if not address and found_eth:
                address = found_eth

            # tìm private key 64 hex
            pk_re = re.compile(r'\b[0-9a-fA-F]{64}\b')
            found_pk = None
            for s in all_strings:
                m = pk_re.search(s)
                if m:
                    found_pk = m.group(0)
                    # prefer keys that are under 'private' words (heuristic)
                    if 'private' in s.lower() or 'priv' in s.lower():
                        found_pk = m.group(0)
                        break
            if not pk and found_pk:
                pk = found_pk

        # Normalise address: ensure it's a 0x-prefixed hex string of 40 bytes
        def _is_valid_eth_address(s):
            if not isinstance(s, str):
                return False
            s = s.strip()
            if s.startswith('0x'):
                hexpart = s[2:]
            else:
                hexpart = s
            return len(hexpart) == 40 and re.fullmatch(r'[0-9a-fA-F]{40}', hexpart) is not None

        if address and isinstance(address, str):
            address = address.strip()
            # If address looks valid already, normalize to lowercase 0x form
            if _is_valid_eth_address(address):
                if not address.startswith('0x'):
                    address = '0x' + address
                address = address.lower()
            else:
                # Try to extract a 0x...40hex substring from any string fields in response
                found = None
                text = json.dumps(data)
                m = re.search(r'0x[0-9a-fA-F]{40}', text)
                if m:
                    found = m.group(0).lower()
                if found:
                    address = found
                else:
                    # leave address as-is (will be validated below)
                    address = address

        # Nếu address không phải dạng ETH (0x...40hex) nhưng private key nhìn giống hex 64,
        # cố gắng suy ra địa chỉ ETH từ private key (fallback).
        def _looks_like_hex_pk(s):
            return isinstance(s, str) and re.fullmatch(r'[0-9a-fA-F]{64}', s.strip()) is not None

        if (not address or not _is_valid_eth_address(address)) and pk and _looks_like_hex_pk(pk):
            # Try to derive ETH address from private key
            derived = None
            try:
                # Try eth_account first
                from eth_account import Account
                acct = Account.from_key('0x' + pk.strip())
                derived = acct.address.lower()
            except Exception:
                try:
                    # Try web3 fallback
                    from web3 import Web3
                    acct = Web3().eth.account.from_key('0x' + pk.strip())
                    derived = acct.address.lower()
                except Exception:
                    derived = None

            if derived and _is_valid_eth_address(derived):
                address = derived

        if not address or not pk or not _is_valid_eth_address(address):
            # Không thấy keys như mong đợi -> trả về nội dung để debug
            snippet = json.dumps(data)[:400]
            msg = (
                "HScoin response missing/invalid address or privateKey. "
                f"Sample: {snippet} -- To auto-derive an ETH address from the private key, "
                "install `eth-account` (pip install eth-account) or `web3`.")
            print(msg)
            return False, msg

        # Trả về dict tiêu chuẩn (address ở dạng '0x' + 40 hexdigits, lowercased)
        return True, {'address': address, 'privateKey': pk}

    except Exception as e:
        msg = f"Lỗi kết nối: {str(e)}"
        print(msg)
        return False, msg