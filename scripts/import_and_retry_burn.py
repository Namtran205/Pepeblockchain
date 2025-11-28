#!/usr/bin/env python3
"""
Import user wallet to HScoin and retry burn once.
Usage: python scripts/import_and_retry_burn.py <user_id> [amount]

This script WILL send the user's private key to HScoin import endpoints (only after you asked for this).
It will NOT print the private key. It prints SHA256 fingerprint and endpoints' responses.
"""
import os
import sys
import json
import re
import time
import hashlib

if len(sys.argv) < 2:
    user_id = 16
else:
    user_id = int(sys.argv[1])

amount = float(sys.argv[2]) if len(sys.argv) >= 3 else 1.0

# project root
this_dir = os.path.dirname(os.path.abspath(__file__))
proj_root = os.path.dirname(this_dir)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pepe.settings')

try:
    import django
    django.setup()
except Exception as e:
    print('Django setup failed:', e)
    raise

from django.db import connection
from django.conf import settings
from accounts.crypto_utils import decrypt_key
import requests

# import call_hscoin function if available
try:
    from accounts.utils import call_hscoin, encode_input_data
except Exception:
    call_hscoin = None
    encode_input_data = None

print('Running import_and_retry_burn for user_id=', user_id)
with connection.cursor() as cursor:
    cursor.execute('SELECT wallet_address, encrypted_private_key FROM students WHERE id = %s', [user_id])
    row = cursor.fetchone()

if not row:
    print('No student row for user id', user_id)
    raise SystemExit(1)

wallet_address, enc_pk = row
print('DB wallet_address:', wallet_address)
print('Encrypted private key preview:', (enc_pk[:80] + '...') if enc_pk else enc_pk)

if not enc_pk:
    print('No encrypted key stored')
    raise SystemExit(1)

try:
    pk = decrypt_key(enc_pk)
except Exception as e:
    print('decrypt_key error:', e)
    raise SystemExit(1)

if not pk:
    print('decrypt_key returned empty')
    raise SystemExit(1)

# normalize pk without 0x for sending
pk_norm = pk.strip()
pk_send = pk_norm[2:] if pk_norm.lower().startswith('0x') else pk_norm

fp = hashlib.sha256(pk_send.encode('utf-8')).hexdigest()
print('Private key fingerprint (SHA256):', fp)

# try derive address
derived = None
try:
    from eth_account import Account
    acct = Account.from_key('0x' + pk_send)
    derived = acct.address.lower()
    print('Derived address:', derived)
except Exception as e:
    try:
        from web3 import Web3
        acct = Web3().eth.account.from_key('0x' + pk_send)
        derived = acct.address.lower()
        print('Derived address (web3):', derived)
    except Exception as e:
        print('Could not derive address:', e)

if derived and wallet_address and derived != wallet_address.lower():
    print('Warning: derived address does not match DB wallet_address')

# HScoin base
base = settings.HSCOIN_API_BASE_URL.rstrip('/')
headers = { 'Content-Type': 'application/json', 'x-api-key': settings.HSCOIN_API_KEY }

candidates = [
    '/import-wallet',
    '/wallet/import',
    '/wallets/import',
    '/wallets',
    '/accounts/import',
    '/generate-wallet',
    '/wallets/add',
]

payloads = [
    { 'address': wallet_address, 'privateKey': pk_send },
    { 'address': wallet_address, 'private_key': pk_send },
    { 'privateKey': pk_send },
    { 'private_key': pk_send },
    { 'key': pk_send, 'address': wallet_address },
]

session = requests.Session()
registered = False
reg_response = None

for path in candidates:
    url = base + path
    for p in payloads:
        try:
            print('\nAttempting import ->', url, 'payload_keys=', list(p.keys()))
            r = session.post(url, json=p, headers=headers, timeout=20)
            body_text = ''
            try:
                body_text = json.dumps(r.json())
            except Exception:
                body_text = (r.text or '')[:2000]
            print('Status:', r.status_code, 'Body preview:', body_text[:1000])

            # check for address in response
            found = None
            m = re.search(r'0x[0-9a-fA-F]{40}', body_text)
            if m:
                found = m.group(0).lower()
            else:
                m2 = re.search(r'(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])', body_text)
                if m2:
                    cand = m2.group(0).lower()
                    if cand == (wallet_address.lower()[2:] if wallet_address.lower().startswith('0x') else wallet_address.lower()):
                        found = '0x' + cand

            if found and (found == wallet_address.lower()):
                print('Import appears to have registered expected address:', found)
                registered = True
                reg_response = { 'url': url, 'status': r.status_code, 'body': body_text }
                break

            if r.status_code in (200,201,409):
                # heuristics: if response JSON contains success=True or ok=True, consider it
                try:
                    j = r.json()
                    if isinstance(j, dict) and ((j.get('success') is True) or (j.get('ok') is True) or (j.get('result') is not None)):
                        print('Import endpoint returned success-like JSON; treating as registered (best-effort)')
                        registered = True
                        reg_response = { 'url': url, 'status': r.status_code, 'body': body_text }
                        break
                except Exception:
                    pass

            # else continue
        except Exception as e:
            print('Request error:', e)
            continue
    if registered:
        break

if not registered:
    print('\nAll import attempts failed. See logs above.\n')
    # Try form-encoded and multipart variants for the most promising endpoints
    print('\nTrying form-encoded and multipart variants (some servers expect form data)...\n')
    form_candidates = ['/import-wallet', '/wallet/import', '/wallets/import', '/accounts/import', '/wallets/add']
    for path in form_candidates:
        url = base + path
        # form-encoded
        for keyname in ['privateKey', 'private_key', 'key']:
            data = { keyname: pk_send, 'address': wallet_address }
            try:
                print('Form POST ->', url, 'data_keys=', list(data.keys()))
                r = session.post(url, data=data, headers=headers, timeout=20)
                body = ''
                try:
                    body = json.dumps(r.json())
                except Exception:
                    body = (r.text or '')[:2000]
                print('Status:', r.status_code, 'Body preview:', body[:1000])
                if r.status_code in (200,201,409):
                    print('Form post returned status', r.status_code)
                    registered = True
                    reg_response = {'url': url, 'status': r.status_code, 'body': body}
                    break
            except Exception as e:
                print('Form post error:', e)
                continue
        if registered:
            break

        # multipart (files)
        try:
            files = { 'private_key': ('key.txt', pk_send) }
            print('Multipart POST ->', url)
            r = session.post(url, files=files, data={'address': wallet_address}, headers=headers, timeout=20)
            body = ''
            try:
                body = json.dumps(r.json())
            except Exception:
                body = (r.text or '')[:2000]
            print('Status:', r.status_code, 'Body preview:', body[:1000])
            if r.status_code in (200,201,409):
                registered = True
                reg_response = {'url': url, 'status': r.status_code, 'body': body}
                break
        except Exception as e:
            print('Multipart error:', e)
            continue

    if not registered:
        print('\nAll form/multipart import attempts failed.\n')
        raise SystemExit(2)

print('\nImport registered at', reg_response['url'], 'status', reg_response['status'])
print('Response preview:', reg_response['body'][:1000])

# If call_hscoin is available, attempt burn via it to reuse existing logic
amount_wei = int(amount * (10 ** 18))
if call_hscoin:
    print('\nAttempting burn via call_hscoin...')
    ok, res = call_hscoin(caller=wallet_address, private_key=pk_send, function_name='burn', args=[amount_wei])
    print('Burn attempt result:', ok, str(res)[:1000])
else:
    # fallback: call HSCOIN execute endpoint directly
    try:
        execute_url = base + '/contracts/0x998161f1ef94f5569155ad830a598909a7ce9a12/execute'
        # build simple inputData manually for burn(uint256)
        # method id for burn(uint256) is 0x42966c68 (assuming signature) - keep using simple encoding
        input_data = '0x42966c680000000000000000000000000000000000000000000000000' + format(amount_wei, 'x').rjust(64, '0')
        payload = { 'caller': wallet_address, 'privateKey': pk_send, 'contractAddress': '0x998161f1ef94f5569155ad830a598909a7ce9a12', 'value': 0, 'inputData': input_data }
        print('Direct execute ->', execute_url)
        r2 = session.post(execute_url, json=payload, headers=headers, timeout=30)
        try:
            print('Execute status:', r2.status_code, 'body:', json.dumps(r2.json()) )
        except Exception:
            print('Execute status:', r2.status_code, 'body_text_preview:', (r2.text or '')[:1000])
    except Exception as e:
        print('Direct execute failed:', e)

print('\nDone.')
