# Generated manually to drop obsolete legacy columns from PostgreSQL

from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0007_alter_perfil_options'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE usuarios_perfil DROP COLUMN IF EXISTS permiso_armeria_editar CASCADE;
            ALTER TABLE usuarios_perfil DROP COLUMN IF EXISTS permiso_armeria_ver CASCADE;
            ALTER TABLE usuarios_perfil DROP COLUMN IF EXISTS permiso_josen_editar CASCADE;
            ALTER TABLE usuarios_perfil DROP COLUMN IF EXISTS permiso_josen_ver CASCADE;
            """,
            reverse_sql=""
        ),
    ]
