from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_student_encrypted_private_key_student_wallet_address'),
    ]

    operations = [
        migrations.RunSQL('''
            CREATE TABLE IF NOT EXISTS unlinked_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                address TEXT NOT NULL,
                unlinked_at DATETIME DEFAULT (datetime('now'))
            );
        ''')
    ]
