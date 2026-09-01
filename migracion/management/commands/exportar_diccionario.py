import csv
import os
from django.core.management.base import BaseCommand
from django.apps import apps

class Command(BaseCommand):
    help = 'Exporta el diccionario de datos de los modelos a un CSV'

    def handle(self, *args, **options):
        output_path = os.path.join('scratch', 'diccionario_postgres.csv')
        os.makedirs('scratch', exist_ok=True)
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['App', 'Tabla (Modelo)', 'Campo', 'Tipo', 'Nulo', 'Foranea', 'Relacion'])

            apps_to_include = ['empresas', 'usuarios', 'productos', 'facturacion', 'tesoreria', 'contable']

            for app_name in apps_to_include:
                app_config = apps.get_app_config(app_name)
                for model in app_config.get_models():
                    model_name = model.__name__
                    for field in model._meta.get_fields():
                        # Solo incluir campos que tienen una columna real en la base de datos (excluye reverse y M2M)
                        if not hasattr(field, 'column') or not field.column:
                            continue
                        
                        field_name = field.name
                        field_type = field.get_internal_type() if hasattr(field, 'get_internal_type') else type(field).__name__
                        
                        is_null = field.null if hasattr(field, 'null') else ''
                        
                        is_fk = field.is_relation and field.many_to_one
                        related_model = ''
                        if is_fk and field.related_model:
                            related_model = field.related_model.__name__

                        writer.writerow([app_name, model_name, field_name, field_type, is_null, is_fk, related_model])
                        
        self.stdout.write(self.style.SUCCESS(f'Diccionario exportado exitosamente a {output_path}'))
