#!/usr/bin/env python3
"""
Test script: simulate a user pasting an address+privateKey by calling the internal logic directly.
Usage: python scripts/paste_link_wallet_test.py --user-id 16 --address 0x... --privateKey <pk>
"""
import os, sys, argparse
this_dir = os.path.dirname(os.path.abspath(__file__))
proj_root = os.path.dirname(this_dir)
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pepe.settings')
import django
django.setup()

from django.db import connection
from accounts.crypto_utils import encrypt_key
from accounts.utils import call_hscoin
import re

parser = argparse.ArgumentParser()
parser.add_argument('--user-id', '-u', type=int, required=True)
parser.add_argument('--address', required=True)
parser.add_argument('--privateKey', required=True)
args = parser.parse_args()

user_id = args.user_id
address = args.address.strip()
pk = args.privateKey.strip()
if not address.startswith('0x'):
    address = '0x' + address
address = address.lower()
if pk.lower().startswith('0x'):
    pk = pk[2:]

# Basic validation
if not re.fullmatch(r'0x[0-9a-fA-F]{40}', address):
    print('Invalid address')
    sys.exit(2)
if not re.fullmatch(r'[0-9a-fA-F]{64}', pk):
    print('Invalid private key')
    sys.exit(2)

# Derive
derived = None
try:
    from eth_account import Account
    derived = Account.from_key('0x'+pk).address.lower()
except Exception:
    try:
        from web3 import Web3
        derived = Web3().eth.account.from_key('0x'+pk).address.lower()
    except Exception:
        derived = None

print('Derived:', derived, 'Matches:', derived==address)

# Save
enc = encrypt_key(pk)
with connection.cursor() as cursor:
    cursor.execute('UPDATE students SET wallet_address=%s, encrypted_private_key=%s WHERE id=%s', [address, enc, user_id])
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO students (id, wallet_address, encrypted_private_key) VALUES (%s,%s,%s)', [user_id, address, enc])
print('Saved to DB (encrypted)')

# Test HScoin caller acceptance
ok, resp = call_hscoin(caller=address, private_key=pk, function_name='balanceOf', args=[address])
print('HScoin test result:', ok, resp)
