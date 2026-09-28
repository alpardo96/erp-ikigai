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

def vaciar_tablas_estudio():
    print("=== LIMPIEZA TOTAL PREVIA DE BASE DE DATOS (ESTUDIO) ===")
    
    # Tablas a limpiar en orden de dependencias
    tablas_a_limpiar = [
        # Tesorería
        'tesoreria_reciboaplicacion',
        'tesoreria_ordenpagoaplicacion',
        'tesoreria_reciboimputacion',
        'tesoreria_ordenpagoimputacion',
        'tesoreria_recibo',
        'tesoreria_ordenpago',
        'tesoreria_valor_terceros',
        'tesoreria_transaccion_bancaria',
        'tesoreria_cobro_tarjeta',
        'tesoreria_movimiento_caja_detalle',
        'tesoreria_movimiento_caja',
        'tesoreria_retirocaja',
        'tesoreria_caja_sesion',
        'tesoreria_tarjeta',
        'cble_cuenta_bancaria',
        'tesoreria_banco',
        'tesoreria_caja',
        
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
        'facturacion_clienteproveedor',
        'facturacion_jurisdiccion',
        
        # Contabilidad y Libro IVA Digital
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
    ]

    with connection.cursor() as cursor:
        for t in tablas_a_limpiar:
            try:
                cursor.execute(f"TRUNCATE TABLE {t} RESTART IDENTITY CASCADE;")
            except Exception as e:
                pass
    print("OK: Tablas operativas, maestros, contabilidad y Libro IVA vaciados para inicio limpio.")

def ejecutar_suite():
    print("==================================================================")
    print(">>> INICIANDO SUITE DE MIGRACION LIMPIA DESDE CERO (ESTUDIO) <<<")
    print("==================================================================")
    
    vaciar_tablas_estudio()

    modulos = [
        ('FASE 0: Base, Sucursales, Ejercicios y Caja', 'migracion.scripts.estudio.00_init_base'),
        ('FASE 1: Maestros, Cuentas, Clientes/Proveedores y Parámetros', 'migracion.scripts.estudio.01_migrar_maestros'),
        ('FASE 2: Asiento de Apertura, Cabeceras y Líneas Contables', 'migracion.scripts.estudio.02_migrar_asientos'),
        ('FASE 3: Tesorería (Bancos, Cuentas, Sesiones, Movimientos, Cheques y Tarjetas)', 'migracion.scripts.estudio.03_migrar_tesoreria'),
        ('FASE 4: Facturación Operativa (Ventas, Compras, Items y Alícuotas)', 'migracion.scripts.estudio.04_migrar_facturacion'),
        ('FASE 5: Cobranzas y Pagos (OPs, Recibos y Aplicaciones)', 'migracion.scripts.estudio.05_migrar_pagos_recibos'),
        ('FASE 6: Libro IVA Digital (LibroIvaCompras, LibroIvaVentas y LibroIvaAlic)', 'migracion.scripts.estudio.07_migrar_lib_iva'),
        ('FASE 7: Auditoría de Integridad y Partida Doble', 'migracion.scripts.estudio.06_verificar_integridad'),
        ('FASE 8: Reseteo de Secuencias PostgreSQL', 'migracion.scripts.reset_sequences'),
    ]

    for titulo, mod_name in modulos:
        print(f"\n------------------------------------------------------------------")
        print(f">>> EJECUTANDO {titulo} <<<")
        print(f"------------------------------------------------------------------")
        mod = importlib.import_module(mod_name)
        if hasattr(mod, 'run'):
            mod.run()
        elif hasattr(mod, 'init_base'):
            mod.init_base()
        elif hasattr(mod, 'reset_sequences'):
            mod.reset_sequences()

    print("\n==================================================================")
    print(">>> MIGRACIÓN COMPLETA DE ESTUDIO FINALIZADA CON ÉXITO <<<")
    print("==================================================================")

if __name__ == '__main__':
    ejecutar_suite()
