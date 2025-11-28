#!/usr/bin/env python3
"""
Test helper: call user_burn_tokens for a given user id and amount.
Usage: python scripts/test_burn.py --user-id 16 --amount 0.001
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
from accounts.utils import user_burn_tokens

parser = argparse.ArgumentParser()
parser.add_argument('--user-id', '-u', type=int, required=True)
parser.add_argument('--amount', '-a', type=float, default=0.001)
args = parser.parse_args()

with connection.cursor() as cursor:
    cursor.execute('SELECT id, wallet_address, encrypted_private_key FROM students WHERE id=%s', [args.user_id])
    row = cursor.fetchone()

if not row:
    print('User not found')
    sys.exit(2)

user_id, addr, enc_pk = row
print('Attempting burn for user', user_id, 'address', addr)
success, result = user_burn_tokens(addr, enc_pk, args.amount)
print('Result:', success, result)
