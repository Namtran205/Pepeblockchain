#!/usr/bin/env python3
"""
Migrate existing students: for each student missing wallet_address or encrypted_private_key,
call HScoin `generate-wallet` via backend utils `hscoin_create_new_wallet()` and save results.

Usage: python scripts/migrate_create_wallets.py [--dry-run]
"""
import os, sys, json, argparse
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
from accounts.utils import hscoin_create_new_wallet
from accounts.crypto_utils import encrypt_key

parser = argparse.ArgumentParser()
parser.add_argument('--dry-run', action='store_true', help='Show what would be done without writing DB')
args = parser.parse_args()

with connection.cursor() as cursor:
    cursor.execute("SELECT id, wallet_address, encrypted_private_key FROM students")
    rows = cursor.fetchall()

count = 0
for row in rows:
    user_id, addr, enc_pk = row
    if addr and enc_pk:
        # already present
        continue
    print('Processing user id', user_id, 'current addr:', addr)
    success, result = hscoin_create_new_wallet()
    if not success:
        print('Failed to create wallet for user', user_id, 'error:', result)
        continue
    new_addr = result.get('address')
    new_pk = result.get('privateKey')
    print('Created wallet:', new_addr)
    if args.dry_run:
        print('Dry-run: would save encrypted pk and address for user', user_id)
    else:
        encrypted = encrypt_key(new_pk)
        with connection.cursor() as cursor:
            cursor.execute('UPDATE students SET wallet_address=%s, encrypted_private_key=%s WHERE id=%s', [new_addr, encrypted, user_id])
            if cursor.rowcount == 0:
                cursor.execute('INSERT INTO students (id, wallet_address, encrypted_private_key) VALUES (%s,%s,%s)', [user_id, new_addr, encrypted])
        print('Saved for user', user_id)
    count += 1

print('Done. wallets created:', count)
