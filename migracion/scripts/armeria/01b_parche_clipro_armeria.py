import os
import sys
import django
from decimal import Decimal
from dbfread import DBF
import pathlib

# Configurar el entorno de Django
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from empresas.models import Empresa
from facturacion.models import ClienteProveedor
from verticalidades.armeria.models import ExtensionArmeria

def run():
    print("Iniciando Parche: Actualización de Campos CLIPRO y ExtensionArmeria")
    
    dir_comercio = r'D:\OneDrive\Escritorio\Migracion\Armeria\Comercio\eje_255'
    clipro_comercio_dbf = os.path.join(dir_comercio, 'cli_pro.dbf')
    
    if not os.path.exists(clipro_comercio_dbf):
        print(f"No se encontró el archivo: {clipro_comercio_dbf}")
        return
        
    empresa = Empresa.objects.get(id=1)
    table = DBF(clipro_comercio_dbf, ignore_missing_memofile=True, encoding='latin1')
    
    clipros_to_update = {}
    extensiones_to_create_or_update = {}
    
    # Pre-cargamos los IDs válidos
    clipro_validos = set(ClienteProveedor.objects.filter(empresa=empresa).values_list('codigo_id', flat=True))
    extensiones_existentes = {ext.cliente_id: ext for ext in ExtensionArmeria.objects.filter(cliente__empresa=empresa)}
    
    count_updated = 0
    
    for row in table:
        codigo = row.get('CODIGO')
        if not codigo or codigo not in clipro_validos:
            continue
            
        # Parse fields from DBF
        contacto = str(row.get('CONTACTO') or '')[:150].strip()
        telefono = str(row.get('TELEFONO') or '')[:100].strip()
        correo = str(row.get('CORREO') or '')[:254].strip()
        tipo_doc_raw = str(row.get('T_DOC') or '').strip()
        if tipo_doc_raw not in ['80', '86', '96', '99']:
            tipo_doc_raw = '80' if str(row.get('CUIT') or '').strip() else '99'
            
        es_policia = bool(row.get('POLICIA'))
        clu = str(row.get('CLU') or '')[:20].strip()
        clu_vto = row.get('CLU_VTO')
        
        # Update ClienteProveedor instance
        cliente = ClienteProveedor.objects.get(codigo_id=codigo)
        cliente.contacto = contacto
        cliente.telefono = telefono
        cliente.correo = correo
        cliente.tipo_documento = tipo_doc_raw
        clipros_to_update[codigo] = cliente
        
        # Update or Create ExtensionArmeria
        ext = extensiones_existentes.get(codigo)
        if ext:
            ext.es_policia = es_policia
            ext.clu = clu
            ext.clu_vto = clu_vto
        else:
            ext = ExtensionArmeria(
                cliente_id=codigo,
                tipo_persona='J' if tipo_doc_raw == '80' else 'F',
                es_policia=es_policia,
                clu=clu,
                clu_vto=clu_vto
            )
        extensiones_to_create_or_update[codigo] = ext
        count_updated += 1

    # Bulk updates
    if clipros_to_update:
        ClienteProveedor.objects.bulk_update(list(clipros_to_update.values()), ['contacto', 'telefono', 'correo', 'tipo_documento'], batch_size=500)
    
    if extensiones_to_create_or_update:
        # Since bulk_update and bulk_create are separate, we separate them
        ext_values = list(extensiones_to_create_or_update.values())
        to_update = [e for e in ext_values if e.id]
        to_create = [e for e in ext_values if not e.id]
        if to_update:
            ExtensionArmeria.objects.bulk_update(to_update, ['es_policia', 'clu', 'clu_vto', 'tipo_persona'], batch_size=500)
        if to_create:
            ExtensionArmeria.objects.bulk_create(to_create, batch_size=500)
            
    print(f"OK {count_updated} registros de ClienteProveedor y ExtensionArmeria procesados/actualizados.")

if __name__ == '__main__':
    run()
