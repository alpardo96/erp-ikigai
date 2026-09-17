import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.management.color import no_style
from django.db import connection
from django.apps import apps

def reset_sequences():
    print("Iniciando reseteo de secuencias en PostgreSQL...")
    models = apps.get_models()
    sequence_sql = connection.ops.sequence_reset_sql(no_style(), models)
    
    if not sequence_sql:
        print("No se encontraron secuencias para actualizar.")
        return

    with connection.cursor() as cursor:
        for sql in sequence_sql:
            try:
                cursor.execute(sql)
            except Exception as e:
                print(f"Error ejecutando: {sql}\nDetalle: {e}")
                
    print("Secuencias actualizadas correctamente. El problema 'ID ya existe' debería estar resuelto.")

if __name__ == '__main__':
    reset_sequences()
