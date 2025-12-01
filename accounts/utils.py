# utils.py
import requests
import json
import re
import logging
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from django.conf import settings

logger = logging.getLogger(__name__)

HSCOIN_ENDPOINT = f"{settings.HSCOIN_API_BASE_URL.rstrip('/')}/contracts/{settings.TOKEN_CONTRACT_ADDRESS}/execute"
HEADERS = {
    "Content-Type": "application/json",
    "x-api-key": settings.HSCOIN_API_KEY
}

# --- Encode ABI ---
def encode_input_data(function_name, args):
    try:
        from web3 import Web3
        from eth_abi import encode
        w3 = Web3()
        types, enc_args = [], []
        for a in args:
            if isinstance(a, int):
                types.append('uint256'); enc_args.append(a)
            elif isinstance(a, str) and re.fullmatch(r'0x[0-9a-fA-F]{40}', a):
                types.append('address'); enc_args.append(w3.to_checksum_address(a))
            else:
                types.append('string'); enc_args.append(a)
        sig = f"{function_name}({','.join(types)})"
        method_id = w3.keccak(text=sig)[:4].hex()
        return '0x' + method_id + encode(types, enc_args).hex()
    except ImportError:
        # Fallback thủ công
        method_ids = {"transfer":"a9059cbb","mint":"40c10f19","burn":"42966c68","balanceOf":"70a08231"}
        mid = method_ids.get(function_name)
        if not mid: raise Exception(f"Manual encode not supported for {function_name}")
        data = mid
        for arg in args:
            if isinstance(arg, int): data += f"{arg:064x}"
            elif isinstance(arg, str) and arg.startswith("0x"): data += arg[2:].rjust(64,'0')
        return '0x' + data

# --- Call HSCOIN API ---
def call_hscoin(caller, function_name, args, private_key=None):
    try:
        hex_input = encode_input_data(function_name, args)
        print("Hex-iput: ",hex_input)
    except Exception as e:
        logger.error(f"Encoding error: {e}")
        return False, str(e)

    payload = {"caller": caller, "contractAddress": settings.TOKEN_CONTRACT_ADDRESS, "value":0, "inputData":hex_input}
    if private_key:
        key = private_key.strip()
        if key.lower().startswith("0x"): key = key[2:]
        payload['privateKey'] = key

    session = requests.Session()
    retries = Retry(total=1, backoff_factor=0.5, status_forcelist=[502,503,504], allowed_methods=["POST"], raise_on_status=False)
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))

    log_payload = dict(payload)
    if 'privateKey' in log_payload: log_payload['privateKey'] = '***'
    logger.info(f"HScoin Call: {function_name} Payload: {log_payload}")

    try:
        res = session.post(HSCOIN_ENDPOINT, json=payload, headers=HEADERS, timeout=30)
        if res.status_code == 200:
            res_json = res.json()
            tx_hash = res_json.get('transactionHash') or res_json.get('hash') or res_json.get('result', {}).get('transactionHash')
            return True, (tx_hash if tx_hash else res_json)
        else:
            return False, f"HScoin Error ({res.status_code}): {res.text}"
    except Exception as e:
        logger.error(f"Connection Error: {e}")
        return False, str(e)

# --- Token operations (updated to use private_key) ---
def admin_mint_tokens(receiver_address, amount):
    # Luôn dùng admin PK
    return call_hscoin(settings.ADMIN_WALLET_ADDRESS, "mint", [receiver_address, int(amount*1e18)], settings.ADMIN_PRIVATE_KEY)

# def user_burn_tokens(user_address, amount, private_key):
#     if not private_key:
#         raise ValueError("Private key của user bắt buộc để burn tokens")

#     bal = hscoin_get_balance(user_address)
#     print("Balance:", bal, "Amount to burn:", amount)
#     if bal < amount:
#         return False, "Insufficient balance"

#     return call_hscoin(user_address, "burn", [int(amount*1e18)], private_key)


# def user_transfer_tokens(sender_address, receiver_address, amount, private_key):
#     if not private_key:
#         raise ValueError("Private key của user bắt buộc để transfer tokens")

#     bal = hscoin_get_balance(sender_address)
#     print("Sender balance:", bal, "Amount to transfer:", amount)
#     if bal < amount:
#         return False, "Insufficient balance"

#     return call_hscoin(sender_address, "transfer", [receiver_address, int(amount*1e18)], private_key)



from decimal import Decimal, getcontext

def user_burn_tokens(user_address, amount, private_key=None):

    pk = private_key or settings.ADMIN_PRIVATE_KEY
    bal = hscoin_get_balance(user_address)
    print("Balance:", bal, "Amount to send:", amount)
    print("Balance token:", bal, "Amount to send:", amount)

    amount_wei = int(Decimal(amount) * Decimal(1e18))
    # if amount_wei > int(Decimal(bal) * Decimal(1e18)):
    #     return False, "Insufficient balance"

    return call_hscoin(user_address, "burn", [amount_wei], pk)

def user_transfer_tokens(sender_address, receiver_address, amount, private_key=None):
    pk = private_key or settings.ADMIN_PRIVATE_KEY
    bal = hscoin_get_balance(sender_address)
    print("Balance token:", bal, "Amount to send:", amount)

    amount_wei = int(Decimal(amount) * Decimal(1e18))
    # if amount_wei > int(Decimal(bal) * Decimal(1e18)):
    #     return False, "Insufficient balance"

    return call_hscoin(sender_address, "transfer", [receiver_address, amount_wei], pk)



# --- Get balance safely ---
# Cấu hình logging để debug nếu cần
logger = logging.getLogger(__name__)

# Đặt độ chính xác cho Decimal
getcontext().prec = 50 

def hscoin_get_balance(user_address): 
    # caller = getattr(settings, 'ADMIN_WALLET_ADDRESS', user_address)
    caller="0x693d7eeac22122406e49df7a84a23382fa272748"
    print(f" Caller: {caller}")
    try:
        hex_input = encode_input_data("getBalance", [user_address])
        print("Hex-input for balanceOf:", hex_input)
        payload = {
            "caller": caller, 
            "contractAddress": settings.TOKEN_CONTRACT_ADDRESS, 
            "value": 0, 
            "inputData": hex_input
        }
        
        res = requests.post(HSCOIN_ENDPOINT, json=payload, headers=HEADERS, timeout=60)
        
        if res.status_code != 200: return 0
        data = res.json()
        print("Response data:", data)
        if data.get("success") is False or "error" in data: return 0

        # ... (Phần tìm val giữ nguyên như câu trả lời trước) ...
        # 1. Tìm giá trị ở cấp cao nhất
        val = data.get("decodedOutput") or data.get("result") or data.get("output")

        # 2. Tìm sâu trong 'data'
        if val is None:
            inner_data = data.get("data")
            if isinstance(inner_data, dict):
                val = inner_data.get("decodedOutput") or inner_data.get("output") or inner_data.get("result") or inner_data.get("returnData")
            elif isinstance(inner_data, (str, int)):
                val = inner_data

        # 3. Check lại lần nữa nếu vẫn là dict
        if isinstance(val, dict):
             val = val.get("output") or val.get("decodedOutput") or val.get("result")

        # ---------------------------------------------------------
        # PHẦN SỬA LỖI QUAN TRỌNG TẠI ĐÂY
        # ---------------------------------------------------------
        int_val = 0
        if isinstance(val, str):
            val = val.strip()
            
            # Trường hợp đặc biệt: "0x" nghĩa là 0
            if val == "0x": 
                int_val = 0
            elif val.startswith("0x"):
                # Chỉ convert nếu có ký tự sau 0x
                try:
                    int_val = int(val, 16)
                except ValueError:
                    int_val = 0
            else:
                try:
                    int_val = int(val)
                except ValueError:
                    int_val = 0
        elif isinstance(val, int):
            int_val = val
            
        balance = Decimal(int_val) / Decimal(10 ** 18)
        print("Balance fetched:", balance)
        return float(balance)

    except Exception as e:
        logger.error(f"Get balance error: {e}")
        return 0

# --- Wallet & transaction logs ---
def hscoin_create_new_wallet():
    url = f"{settings.HSCOIN_API_BASE_URL.rstrip('/')}/generate-wallet"
    try:
        res = requests.post(url, json={}, headers=HEADERS, timeout=15)
        return (True,res.json()) if res.status_code==200 else (False,res.text)
    except Exception as e: return False,str(e)

def _tx_log_path(user_id):
    base = getattr(settings,'MEDIA_ROOT',os.path.join(os.getcwd(),'media'))
    folder = os.path.join(base,'tx_logs')
    os.makedirs(folder,exist_ok=True)
    return os.path.join(folder,f'user_{user_id}_txs.json')

def append_user_tx(user_id, entry):
    from datetime import datetime
    if 'ts' not in entry: entry['ts'] = datetime.utcnow().isoformat()+'Z'
    path = _tx_log_path(user_id)
    try:
        data = []
        if os.path.exists(path):
            with open(path,'r',encoding='utf-8') as f: data=json.load(f)
        data.insert(0,entry)
        data=data[:200]
        with open(path,'w',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False,indent=2)
    except Exception as e:
        logger.error('Failed to write tx log for %s: %s', user_id, e)

def read_user_txs(user_id, limit=50):
    path = _tx_log_path(user_id)
    try:
        if os.path.exists(path):
            with open(path,'r',encoding='utf-8') as f:
                data=json.load(f)
                return data[:limit]
    except Exception as e:
        logger.error('Failed to read tx log for %s: %s', user_id, e)
    return []
