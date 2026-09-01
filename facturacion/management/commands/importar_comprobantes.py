import csv
from django.core.management.base import BaseCommand, CommandError
from facturacion.models import TipoComprobante

class Command(BaseCommand):
    help = 'Importa los Tipos de Comprobantes desde un archivo CSV proporcionado por ARCA'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Ruta absoluta al archivo CSV (ej: c:\\borrador\\comprobantes.csv)')

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        
        try:
            with open(csv_path, mode='r', encoding='utf-8') as file:
                # Utilizamos DictReader, pero el CSV no tiene headers con un nombre estándar fijo, 
                # así que pasamos los nombres de los campos si es necesario.
                # El archivo original tiene: codigo,descripcion,signo en la primer linea.
                reader = csv.DictReader(file)
                
                # Normalizar nombres de columnas por posibles espacios o mayúsculas en el header
                # Asumimos que los headers son exactamente "codigo", "descripcion", "signo"
                
                creados = 0
                actualizados = 0
                
                for linea, row in enumerate(reader, start=2):
                    try:
                        codigo_crudo = row.get('codigo', '').strip()
                        descripcion = row.get('descripcion', '').strip()
                        signo_crudo = row.get('signo', '1').strip()
                        
                        if not codigo_crudo:
                            self.stdout.write(self.style.WARNING(f"Línea {linea}: Código vacío, saltando."))
                            continue
                            
                        # Formatear el código a 3 dígitos (ej: "1" -> "001")
                        codigo = str(codigo_crudo).zfill(3)
                        
                        # Truncar la descripción a 100 caracteres
                        detalle = descripcion[:100]
                        
                        # Convertir signo
                        signo = int(signo_crudo) if signo_crudo else 1
                        
                        # Determinar estado: True para 001 a 008, False para el resto
                        estado = True if codigo in ["001", "002", "003", "004", "005", "006", "007", "008"] else False
                        
                        # Actualizar o Crear en la Base de Datos
                        obj, created = TipoComprobante.objects.update_or_create(
                            codigo=codigo,
                            defaults={
                                'detalle': detalle,
                                'signo': signo,
                                'estado': estado
                            }
                        )
                        
                        if created:
                            creados += 1
                        else:
                            actualizados += 1
                            
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error procesando la línea {linea}: {str(e)}"))
                
                self.stdout.write(self.style.SUCCESS(f"Importación finalizada. Creados: {creados}. Actualizados: {actualizados}."))
                
        except FileNotFoundError:
            raise CommandError(f'El archivo "{csv_path}" no existe.')
        except Exception as e:
            raise CommandError(f'Ocurrió un error inesperado al leer el archivo: {str(e)}')
