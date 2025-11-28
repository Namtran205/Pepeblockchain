import re
import json
import requests
from pathlib import Path

# Load settings values
repo_root = Path(__file__).resolve().parent.parent
settings_file = repo_root / 'pepe' / 'settings.py'
text = settings_file.read_text(encoding='utf-8')

def get_val(name):
    m = re.search(rf"^{name}\s*=\s*(.+)$", text, re.M)
    if not m:
        return None
    val = m.group(1).strip()
    try:
        return eval(val)
    except Exception:
        return val.strip().strip('"\'')

HSCOIN_API_BASE_URL = get_val('HSCOIN_API_BASE_URL')
HSCOIN_API_KEY = get_val('HSCOIN_API_KEY')
ADMIN_WALLET_ADDRESS = get_val('ADMIN_WALLET_ADDRESS')
ADMIN_PRIVATE_KEY = get_val('ADMIN_PRIVATE_KEY')
TOKEN_CONTRACT_ADDRESS = get_val('TOKEN_CONTRACT_ADDRESS')

print('Endpoint base:', HSCOIN_API_BASE_URL)
contract = TOKEN_CONTRACT_ADDRESS
api_url = HSCOIN_API_BASE_URL.rstrip('/') + f'/contracts/{contract}/execute'

headers = {'Content-Type':'application/json', 'x-api-key': HSCOIN_API_KEY}

try:
    from web3 import Web3
except Exception:
    Web3 = None

# Build ABI-encoded call data for balanceOf(address):
def build_balance_of_data(address):
    a = (address or '').lower().replace('0x','')
    if Web3 is None:
        # fallback: compute keccak using built-in hashlib if eth-utils not present
        try:
            from eth_utils import keccak
            selector = keccak(text='balanceOf(address)')[:4].hex()
        except Exception:
            raise RuntimeError('web3 or eth_utils required to encode ABI')
    else:
        selector = Web3.keccak(text='balanceOf(address)')[:4].hex()
    arg = a.rjust(64, '0')
    return '0x' + selector + arg

data_hex = build_balance_of_data(ADMIN_WALLET_ADDRESS)

payload = {
    'caller': ADMIN_WALLET_ADDRESS,
    'privateKey': ADMIN_PRIVATE_KEY,
    'contractAddress': TOKEN_CONTRACT_ADDRESS,
    'value': 0,
    'inputData': data_hex
}

print('\nPOST', api_url)
try:
    resp = requests.post(api_url, json=payload, headers=headers, timeout=20)
    print('Status:', resp.status_code)
    print('Headers:', {k: resp.headers.get(k) for k in ('content-type','date','server')})
    try:
        print('JSON body:\n', json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print('Text body:\n', resp.text)
except Exception as e:
    print('Request failed:', e)
    raise
