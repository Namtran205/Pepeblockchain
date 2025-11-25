from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_rawsql_tables'),
    ]

    operations = [
        migrations.RunSQL("""
            ALTER TABLE users ADD COLUMN coins INTEGER DEFAULT 0;
            ALTER TABLE users ADD COLUMN last_checkin DATE;
        """),
    ]
