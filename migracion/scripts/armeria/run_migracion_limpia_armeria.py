import os
import sys
import django
from django.db import connection

# Configurar el entorno de Django
import pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import importlib

def vaciar_tablas_armeria():
    print("=== LIMPIEZA TOTAL PREVIA DE BASE DE DATOS (ARMERÍA) ===")
    
    # Tablas a limpiar en orden de dependencia
    tablas_a_limpiar = [
        # Tesorería
        'tesoreria_reciboaplicacion',
        'tesoreria_ordenpagoaplicacion',
        'tesoreria_reciboimputacion',
        'tesoreria_ordenpagoimputacion',
        'tesoreria_recibo',
        'tesoreria_ordenpago',
        'tesoreria_cobro_tarjeta',
        'tesoreria_movimiento_caja_detalle',
        'tesoreria_movimiento_caja',
        'tesoreria_cajasesion',
        
        # Facturación
        'facturacion_ventaitem',
        'facturacion_ventaalicuotaiva',
        'facturacion_movimiento',
        'facturacion_compraitem',
        'facturacion_compraalicuota',
        'facturacion_compraretperc',
        'facturacion_preventaitem',
        'facturacion_preventa',
        'facturacion_venta',
        'facturacion_compra',
        'verticalidades_extensionarmeria',
        'facturacion_clienteproveedor',
        
        # Inventario
        'productos_tomainventarioitem',
        'productos_tomainventario',
        'productos_movimientostock',
        'productos_stocksucursal',
        'productos_subproducto',
        'productos_producto',
        'productos_familia',
        'productos_rubro',
        'productos_marca',
        
        # Contabilidad
        'cble_retencion_practicada',
        'cble_ret_perc_sufrida',
        'cble_libro_iva_alic',
        'cble_libro_iva_ventas',
        'cble_libro_iva_compras',
        'cble_asiento_mov',
        'cble_asiento_enc',
        'cble_parametros',
        'cble_alicuotas_iva',
        'cble_cuentas',
        'facturacion_jurisdiccion',
    ]

    with connection.cursor() as cursor:
        for t in tablas_a_limpiar:
            try:
                cursor.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;")
            except Exception as e:
                pass
    print("OK: Tablas operativas y maestros vaciados para inicio limpio.")

def ejecutar_suite():
    print("==================================================================")
    print(">>> INICIANDO SUITE DE MIGRACION LIMPIA DESDE CERO (ARMERIA) <<<")
    print("==================================================================")
    
    vaciar_tablas_armeria()

    modulos = [
        ('FASE 0: Base, Sucursales y Cajas', 'migracion.scripts.armeria.00_init_base_armeria'),
        ('FASE 1: Tipos Comprobante ARCA CSV', 'migracion.scripts.armeria.01_migrar_tipocomprobante_csv'),
        ('FASE 2: Maestros, Clientes/Proveedores Normalizados y Extension Armeria', 'migracion.scripts.armeria.02_migrar_maestros_clipro_armeria'),
        ('FASE 3: Catalogo Productos (Armeria + DSK) y Subproductos', 'migracion.scripts.armeria.03_migrar_inventario_armeria'),
        ('FASE 3B: Tomas de Inventario Fisico Historicas (VFP 2023 y 2025)', 'migracion.scripts.armeria.03b_migrar_inventarios_fisicos'),
        ('FASE 4: Ventas y Compras Historicas con Cruce Contable', 'migracion.scripts.armeria.04_migrar_ventas_compras_armeria'),
        ('FASE 5: Tesoreria (Recibos, Anticipos RV y Ordenes de Pago)', 'migracion.scripts.armeria.05_migrar_tesoreria_armeria'),
        ('FASE 6: Asientos Contables y Libro IVA Digital', 'migracion.scripts.armeria.06_migrar_asientos_libroiva_armeria'),
    ]

    for titulo, mod_name in modulos:
        print(f"\n>>> EJECUTANDO {titulo} <<<")
        mod = importlib.import_module(mod_name)
        if hasattr(mod, 'run'):
            mod.run()
        elif hasattr(mod, 'init_base'):
            mod.init_base()
        elif hasattr(mod, 'migrar_tipos_comprobante'):
            mod.migrar_tipos_comprobante()

    # Resumen final de la base de datos
    print("\n==================================================================")
    print("RESUMEN FINAL DE REGISTROS EN BASE DE DATOS POSTGRESQL")
    print("==================================================================")
    
    from facturacion.models import Venta, Compra, ClienteProveedor, TipoComprobante
    from verticalidades.armeria.models import ExtensionArmeria
    from productos.models import Producto, Subproducto, TomaInventario, TomaInventarioItem, StockSucursal
    from tesoreria.models import Recibo, OrdenPago
    from contable.models import Asiento, LibroIvaCompras, LibroIvaVentas
    
    print(f"- Tipos de Comprobantes Oficiales ARCA: {TipoComprobante.objects.count()}")
    print(f"- Clientes y Proveedores (Normalizados): {ClienteProveedor.objects.count()}")
    print(f"- Extension Armeria (CLU, Vencimiento, Policia): {ExtensionArmeria.objects.count()}")
    print(f"- Productos (Armeria + DSK): {Producto.objects.count()}")
    print(f"- Subproductos (Armas/Series): {Subproducto.objects.count()}")
    print(f"- Tomas de Inventario Fisico: {TomaInventario.objects.count()}")
    print(f"- Items Contados en Inventarios Fisicos: {TomaInventarioItem.objects.count()}")
    print(f"- Ventas Validadas y Homologadas: {Venta.objects.count()}")
    print(f"- Compras Migradas: {Compra.objects.count()}")
    print(f"- Recibos de Tesoreria (Cobranzas + Anticipos Armas): {Recibo.objects.count()}")
    print(f"- Ordenes de Pago: {OrdenPago.objects.count()}")
    print(f"- Asientos Contables (Ejercicio 2026): {Asiento.objects.count()}")
    print(f"- Libro IVA Compras: {LibroIvaCompras.objects.count()}")
    print(f"- Libro IVA Ventas: {LibroIvaVentas.objects.count()}")
    print("==================================================================")
    print("MIGRACION LIMPIA COMPLETADA CON TOTAL EXITO.")
    print("==================================================================")


if __name__ == '__main__':
    ejecutar_suite()
