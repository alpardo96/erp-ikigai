# Plan de Re-Migración Limpia y Consolidada - Vertical Estudio (`eje_272`)

## 1. Contexto y Objetivos
Se ejecutó una migración desde cero (limpia) en la base de datos `erp-Ikigai-Estudio` a partir de los datos históricos del lote FoxPro (`D:\OneDrive\Escritorio\Migracion\Estudio\eje_272`).
Se consolidaron todas las lecciones aprendidas y correcciones de la primera migración, incluyendo los módulos operativos de facturación y los modelos fiscales del Libro IVA Digital de ARCA.

## 2. Acciones y Arquitectura de la Migración

### A. Limpieza Previa (`vaciar_tablas_estudio`)
Se truncaron las tablas operativas de la base de datos en orden de dependencias respetando claves foráneas:
- **Tesorería:** `tesoreria_reciboaplicacion`, `tesoreria_ordenpagoaplicacion`, `tesoreria_reciboimputacion`, `tesoreria_ordenpagoimputacion`, `tesoreria_recibo`, `tesoreria_ordenpago`, `tesoreria_transaccion_bancaria`, `tesoreria_valor_terceros`, `tesoreria_cobro_tarjeta`, `tesoreria_movimiento_caja_detalle`, `tesoreria_movimiento_caja`, `tesoreria_cajasesion`, `cble_cuenta_bancaria`, `tesoreria_tarjeta`, `tesoreria_banco`, `tesoreria_caja`.
- **Facturación:** `facturacion_ventaitem`, `facturacion_ventaalicuotaiva`, `facturacion_movimiento`, `facturacion_compraitem`, `facturacion_compraalicuota`, `facturacion_compraretperc`, `facturacion_preventaitem`, `facturacion_preventa`, `facturacion_venta`, `facturacion_compra`, `facturacion_clienteproveedor`, `facturacion_jurisdiccion`.
- **Contabilidad y Libro IVA Digital:** `cble_retencion_practicada`, `cble_ret_perc_sufrida`, `cble_libro_iva_alic`, `cble_libro_iva_ventas`, `cble_libro_iva_compras`, `cble_asiento_mov`, `cble_asiento_enc`, `cble_parametros`, `cble_alicuotas_iva`, `cble_cuentas`.
- **Empresas:** Mantener o inicializar las entidades de Empresa `Lopez Rios y Asoc SA`, Sucursal `Casa Central` y Ejercicios 2026 / 2027.

### B. Módulos de Migración Consolidados

1. **`00_init_base.py`:**
   - Creación de Superusuario `Ikigai`.
   - Empresa 1 (`Lopez Rios y Asoc SA`, CUIT `30708395206`).
   - Sucursal 1 (`Casa Central`, punto 1).
   - Ejercicio 1 (2026: `2025-06-01` a `2026-05-31`) y Ejercicio 2 (2027: `2026-06-01` a `2027-05-31`).
   - Caja 1 (`Caja Principal`, tipo `T`).
   - Producto 1 (`Honorarios / Servicios Contables`, tipo `2` Servicio).

2. **`01_migrar_maestros.py`:**
   - Cuentas Contables (`cuentas.dbf`, 247 registros, tipos contables `A`/`P`/`N`/`R` jerárquicos).
   - Jurisdicciones (`provincias.dbf`, 24 registros).
   - Alícuotas IVA (`alicuotas_iva.dbf`, 6 registros).
   - Clientes/Proveedores (`cli_pro.dbf`, 387 registros con `tipo_entidad` = `CLI_PRO` 1 o 2, condición IVA `INSC_IVA`).
   - Parámetros Contables (`parametros_contables.dbf`).

3. **`02_migrar_asientos.py`:**
   - Asiento de Apertura (`apertura.dbf`, 68 líneas, balanceo partida doble).
   - Cabeceras de Asientos (`asto_enc.dbf`, 1.817 registros vinculados por fecha al ejercicio).
   - Líneas de Asientos (`asto_mov.dbf`, normalización de débitos/créditos negativos y constraint `debe_xor_haber`).

4. **`03_migrar_tesoreria.py`:**
   - Bancos (`bancos.dbf`, 82 registros).
   - Cuentas Bancarias (`cta_cte.dbf`, 3 registros).
   - Tarjetas (`tarjetas.dbf`, 5 registros).
   - Sesiones de Caja (`enc_caja_diaria.dbf`, 323 sesiones).
   - Movimientos de Caja (`caja_diaria.dbf`, 4.293 registros vinculando `cuenta_id`, `cli_pro_id`, `asiento_id` y forzando `condic=1`).
   - Valores de Terceros (`valores_terceros.dbf`, 1.173 cheques de cartera).
   - Transacciones Bancarias / Cheques Propios (`cheques.dbf`, 428 registros).
   - Cobros con Tarjeta (`tarjetas_mov.dbf`, 209 cupones).

5. **`04_migrar_facturacion.py`:**
   - Ventas y Compras operativas (`lib_iva.dbf`, 2.959 comprobantes).
   - Mapeo de `TipoComprobante` por código fiscal AFIP / `COD_CITI`.
   - Generación de `VentaItem` y `CompraItem` vinculados al Producto 1.
   - Actualización de CAE (`lib_iva_afip.dbf`).
   - Alícuotas operativas de IVA (`lib_iva_alic.dbf`).

6. **`05_migrar_pagos_recibos.py`:**
   - Órdenes de Pago (`ord_pago.dbf`, 2.606 registros).
   - Recibos (`recibos.dbf`, 1.688 registros).
   - Imputaciones / Aplicaciones a Comprobantes (`ord_pago_facturas.dbf`, 2.540 registros).

7. **`07_migrar_lib_iva.py`:**
   - Libro IVA Compras (`LibroIvaCompras`, 517 registros).
   - Libro IVA Ventas (`LibroIvaVentas`, 2.417 registros).
   - Alícuotas fiscales ARCA (`LibroIvaAlic`, 328 registros).

8. **`06_verificar_integridad.py`:**
   - Auditoría 100% estricta de partida doble (asientos desbalanceados).
   - Resumen volumétrico integral.

9. **`reset_sequences.py`:**
   - Reseteo integral de secuencias en PostgreSQL.

10. **`run_migracion_limpia_estudio.py`:**
    - Orquestador integral que ejecuta la limpieza previa y todas las fases secuencialmente.
