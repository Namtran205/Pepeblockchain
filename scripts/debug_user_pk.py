#!/usr/bin/env python3
"""
Debug helper: decrypt a user's encrypted private key and print SHA256 fingerprint + derived address.
Will NOT print the raw private key.
Usage: python scripts/debug_user_pk.py --user-id 16
"""
import os, sys, argparse, hashlib
this_dir = os.path.dirname(os.path.abspath(__file__))
proj_root = os.path.dirname(this_dir)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pepe.settings')
try:
    import django
    django.setup()
except Exception as e:
    print('Failed to setup Django:', e)
    raise

from django.db import connection
from accounts.crypto_utils import decrypt_key

parser = argparse.ArgumentParser()
parser.add_argument('--user-id', '-u', type=int, required=True)
args = parser.parse_args()

user_id = args.user_id
with connection.cursor() as cursor:
    cursor.execute('SELECT id, wallet_address, encrypted_private_key FROM students WHERE id=%s', [user_id])
    row = cursor.fetchone()

if not row:
    print('User not found:', user_id)
    sys.exit(2)

uid, db_addr, enc_pk = row
if not enc_pk:
    print('No encrypted private key for user', uid)
    sys.exit(0)

try:
    pk = decrypt_key(enc_pk)
except Exception as e:
    print('Failed to decrypt key:', e)
    sys.exit(1)

# compute fingerprint (sha256 of raw pk) but DO NOT print pk
fp = hashlib.sha256(pk.encode('utf-8')).hexdigest()

# derive address safely (without displaying pk)
derived = None
try:
    from eth_account import Account
    derived = Account.from_key('0x' + pk.strip()).address.lower()
except Exception:
    try:
        from web3 import Web3
        derived = Web3().eth.account.from_key('0x' + pk.strip()).address.lower()
    except Exception:
        derived = None

print('User id:', uid)
print('DB wallet_address:', db_addr)
print('Decrypted private key length:', len(pk) if isinstance(pk, str) else 'N/A')
print('SHA256 fingerprint (private key):', fp)
print('Derived address (from decrypted pk):', derived)
print('Match with DB address:', str(derived == (db_addr.lower() if db_addr else None)))
