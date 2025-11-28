import re
import json
import requests
from pathlib import Path

# Locate settings.py relative to repo
repo_root = Path(__file__).resolve().parent.parent
settings_file = repo_root / 'pepe' / 'settings.py'

if not settings_file.exists():
    print('Could not find pepe/settings.py at', settings_file)
    raise SystemExit(1)

text = settings_file.read_text(encoding='utf-8')

def get_val(name):
    m = re.search(rf"^{name}\s*=\s*(.+)$", text, re.M)
    if not m:
        return None
    val = m.group(1).strip()
    try:
        return eval(val)
    except Exception:
        # fallback: strip surrounding quotes if any
        return val.strip().strip('"\'')

HSCOIN_API_BASE_URL = get_val('HSCOIN_API_BASE_URL')
HSCOIN_API_KEY = get_val('HSCOIN_API_KEY')
ADMIN_WALLET_ADDRESS = get_val('ADMIN_WALLET_ADDRESS')
TOKEN_CONTRACT_ADDRESS = get_val('TOKEN_CONTRACT_ADDRESS')

print('Using HSCOIN_API_BASE_URL=', HSCOIN_API_BASE_URL)
print('Using HSCOIN_API_KEY=', HSCOIN_API_KEY and ('<present>' if HSCOIN_API_KEY else '<missing>'))
print('Using ADMIN_WALLET_ADDRESS=', ADMIN_WALLET_ADDRESS)
print('Using TOKEN_CONTRACT_ADDRESS=', TOKEN_CONTRACT_ADDRESS)

if not HSCOIN_API_BASE_URL or not HSCOIN_API_KEY:
    print('Missing HScoin config; aborting')
    raise SystemExit(2)

api_url = HSCOIN_API_BASE_URL.rstrip('/') + '/smart-contract/execute'
headers = {
    'Content-Type': 'application/json',
    'x-api-key': HSCOIN_API_KEY
}

payload = {
    'caller': ADMIN_WALLET_ADDRESS or '',
    'contractAddress': TOKEN_CONTRACT_ADDRESS,
    'value': 0,
    'inputData': {
        'function': 'balanceOf',
        'args': [ADMIN_WALLET_ADDRESS or '']
    }
}

print('\nPOST', api_url)
print('Payload (redacted):', json.dumps({**payload, 'caller': payload['caller']}, ensure_ascii=False))

try:
    resp = requests.post(api_url, json=payload, headers=headers, timeout=20)
    print('\nStatus:', resp.status_code)
    print('Response headers:')
    for k in ('content-type','date','server'):
        if k in resp.headers:
            print(' ', k+':', resp.headers.get(k))
    print('\nResponse body (full):')
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(resp.text)
except Exception as e:
    print('Request failed:', e)
    raise
