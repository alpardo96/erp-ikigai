"""
Script de migración directa de Tarifas de Estudio (facturacion_tarifaestudio)
desde la base de datos local 'facturacion' (localhost) hacia la base de datos activa del Estudio.
"""
import os
import sys
import django
import psycopg2
from decimal import Decimal

# Configuración del entorno Django
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import transaction
from empresas.models import Empresa
from verticalidades.estudio.models import TarifaEstudio
from facturacion.models import ClienteProveedor
from productos.models import Producto
from contable.models import Cuenta


def migrar_tarifas_estudio():
    print("=" * 70)
    print("INICIANDO MIGRACIÓN DE TARIFAS DE ESTUDIO (facturacion_tarifaestudio)")
    print("=" * 70)

    # 1. Obtener Empresa Destino
    empresa_destino = Empresa.objects.filter(pk=1).first() or Empresa.objects.first()
    if not empresa_destino:
        print("ERROR: No se encontró la empresa de Estudio en la base de datos destino.")
        return

    print(f"Empresa Destino: [{empresa_destino.pk}] {empresa_destino.nombre} (CUIT: {empresa_destino.cuit})")

    # 2. Conectar a la Base de Datos Origen (localhost:facturacion)
    try:
        conn_origen = psycopg2.connect(
            host='localhost',
            port=5432,
            user='ikigai',
            password='DhiQY',
            dbname='facturacion'
        )
        cur_origen = conn_origen.cursor()
    except Exception as e:
        print(f"ERROR: No se pudo conectar a PostgreSQL localhost/facturacion: {e}")
        return

    # 3. Consultar tarifas origen junto a maestros para resolución robusta
    query_origen = """
        SELECT 
            t.id,
            t.cliente_id,
            c.codigo_anterior as cli_cod_ant,
            c.razon_social as cli_razon_social,
            c.cuit as cli_cuit,
            t.producto_id,
            p.detalle as prod_detalle,
            t.cuenta_id,
            cu.jerarquia as cu_jerarquia,
            cu.cuenta as cu_nombre,
            t.tarifa_f,
            t.tarifa_p,
            t.activo
        FROM facturacion_tarifaestudio t
        LEFT JOIN facturacion_clienteproveedor c ON t.cliente_id = c.codigo_id
        LEFT JOIN productos_producto p ON t.producto_id = p.id
        LEFT JOIN cble_cuentas cu ON t.cuenta_id = cu.id
        WHERE t.empresa_id = 3
        ORDER BY t.id
    """
    cur_origen.execute(query_origen)
    filas_origen = cur_origen.fetchall()
    conn_origen.close()

    print(f"Tarifas leídas desde base origen: {len(filas_origen)}")

    # 4. Resolver Producto Destino (Honorarios del Estudio)
    producto_destino = (
        Producto.objects.filter(empresa=empresa_destino, detalle__icontains="HONORARIOS").first()
        or Producto.objects.filter(empresa=empresa_destino, pk=1).first()
        or Producto.objects.filter(empresa=empresa_destino).first()
    )
    if not producto_destino:
        print("ERROR: No se encontró ningún producto de servicios en la empresa destino.")
        return

    print(f"Producto Destino asignado: [{producto_destino.id}] {producto_destino.detalle}")

    # 5. Migración Atómica
    migrados = 0
    actualizados = 0
    errores = []

    with transaction.atomic():
        # Limpiamos tarifas previas si existiesen para evitar duplicaciones
        TarifaEstudio.objects.filter(empresa=empresa_destino).delete()

        for fila in filas_origen:
            (
                t_id, c_id, c_cod_ant, c_rz, c_cuit,
                p_id, p_det,
                cu_id, cu_jer, cu_nom,
                tarifa_f, tarifa_p, activo
            ) = fila

            # Resolución del Cliente en Destino
            cuit_limpio = ''.join(filter(str.isdigit, str(c_cuit or '')))
            cliente_dest = None

            if cuit_limpio and cuit_limpio not in ('0', ''):
                cliente_dest = ClienteProveedor.objects.filter(empresa=empresa_destino, cuit=cuit_limpio).first()

            if not cliente_dest and c_cod_ant:
                cliente_dest = (
                    ClienteProveedor.objects.filter(empresa=empresa_destino, codigo_anterior=c_cod_ant).first()
                    or ClienteProveedor.objects.filter(empresa=empresa_destino, codigo_id=c_cod_ant).first()
                )

            if not cliente_dest and c_id:
                cliente_dest = ClienteProveedor.objects.filter(empresa=empresa_destino, codigo_id=c_id).first()

            if not cliente_dest and c_rz:
                cliente_dest = ClienteProveedor.objects.filter(empresa=empresa_destino, razon_social__iexact=c_rz.strip()).first()

            if not cliente_dest:
                errores.append(f"Tarifa ID {t_id}: No se encontró el cliente '{c_rz}' (CUIT: {c_cuit}, CodAnt: {c_cod_ant})")
                continue

            # Resolución de la Cuenta Contable en Destino
            cuenta_dest = None
            if cu_jer:
                cuenta_dest = Cuenta.objects.filter(empresa=empresa_destino, jerarquia=cu_jer.strip()).first()

            # Creación del registro TarifaEstudio
            TarifaEstudio.objects.create(
                empresa=empresa_destino,
                cliente=cliente_dest,
                producto=producto_destino,
                cuenta=cuenta_dest,
                tarifa_f=Decimal(str(tarifa_f or 0)),
                tarifa_p=Decimal(str(tarifa_p or 0)),
                activo=bool(activo) if activo is not None else True
            )
            migrados += 1

    print("-" * 70)
    print(f"RESULTADO DE LA MIGRACIÓN:")
    print(f"Tarifas migradas exitosamente: {migrados} de {len(filas_origen)}")
    if errores:
        print(f"Advertencias / Errores ({len(errores)}):")
        for err in errores:
            print(f" - {err}")
    print("=" * 70)


if __name__ == '__main__':
    migrar_tarifas_estudio()
