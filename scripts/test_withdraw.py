#!/usr/bin/env python3
"""
Test admin mint (withdraw) to a user address.
Usage: python scripts/test_withdraw.py --user-id 16 --amount 0.0001
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
from accounts.utils import admin_mint_tokens

parser = argparse.ArgumentParser()
parser.add_argument('--user-id', '-u', type=int, required=True)
parser.add_argument('--amount', '-a', type=float, default=0.0001)
args = parser.parse_args()

with connection.cursor() as cursor:
    cursor.execute('SELECT wallet_address FROM students WHERE id=%s', [args.user_id])
    row = cursor.fetchone()

if not row:
    print('User not found or no wallet')
    sys.exit(2)

addr = row[0]
print('Minting to', addr)
ok, res = admin_mint_tokens(addr, args.amount)
print('Result:', ok, res)
