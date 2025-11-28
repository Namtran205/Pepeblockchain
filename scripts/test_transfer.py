#!/usr/bin/env python3
"""
Test user transfer: sender user id sends tokens to receiver address.
Usage: python scripts/test_transfer.py --sender 16 --receiver 2 --amount 0.0001
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
from accounts.utils import user_transfer_tokens

parser = argparse.ArgumentParser()
parser.add_argument('--sender', type=int, required=True)
parser.add_argument('--receiver', type=int, required=True)
parser.add_argument('--amount', type=float, default=0.0001)
args = parser.parse_args()

with connection.cursor() as cursor:
    cursor.execute('SELECT wallet_address, encrypted_private_key FROM students WHERE id=%s', [args.sender])
    row = cursor.fetchone()

if not row:
    print('Sender not found or no wallet')
    sys.exit(2)

sender_addr, enc_pk = row
# Receiver: fetch wallet_address
with connection.cursor() as cursor:
    cursor.execute('SELECT wallet_address FROM students WHERE id=%s', [args.receiver])
    r = cursor.fetchone()
if not r:
    print('Receiver not found or no wallet')
    sys.exit(2)
receiver_addr = r[0]
print('Transfer from', sender_addr, 'to', receiver_addr)
ok, res = user_transfer_tokens(sender_addr, enc_pk, receiver_addr, args.amount)
print('Result:', ok, res)
