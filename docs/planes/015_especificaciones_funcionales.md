# Plan 015 — Especificaciones de Requerimientos Funcionales (Ventas, Compras, Tesorería)

## Estado: ✅ Completado

## Objetivo
Estandarizar los flujos de captura de transacciones comerciales de Ventas y Compras, y la gestión de Cobros y Pagos (Tesorería), garantizando trazabilidad contable, automatización de stock y cumplimiento normativo.

## IV. ESPECIFICACIÓN DE REQUERIMIENTOS FUNCIONALES (VENTAS Y COMPRAS)

### 1. Introducción
Objetivo de los Módulos: Estandarizar los flujos de captura de transacciones comerciales de Ventas y Compras, garantizando la trazabilidad contable absoluta, la automatización en la gestión de stock y el cumplimiento normativo ante ARCA.

### 2. Arquitectura de Datos y Estructura Transaccional
Separación de Entidades: El sistema debe mantener una separación estricta entre cabeceras (_enc) y movimientos (_mov / ítems) para soportar la integridad referencial.
Ventas con Productos: La imputación contable se deriva a nivel de línea en ventas_mov.
Ventas de Servicios/Gastos: La imputación se define globalmente en la cabecera (ventas_enc o lib_iva).

### 3. Flujos de Trabajo y Automatización de Procesos
Gestión de Ventas:
Facturación Electrónica: Integración con Web Services de ARCA para obtención de CAE. Incluye facturación directa, carga de puntos de venta externos y emisión por lotes para servicios recurrentes (ej. Colegio).
Facturación Manual: Carga diferida de comprobantes emitidos en plataformas externas o liquidaciones de terceros.
Gestión de Compras:
Carga Inteligente (OCR/PDF): Automatización mediante lectura de archivos PDF en carpetas monitoreadas. El sistema debe resolver la imputación contable basándose en los parámetros del rubro del producto y los indicadores impositivos globales.
Carga Rápida de Gastos: Interfaz simplificada desde Caja Diaria para rendiciones de gastos menores sin gestión de stock.
Selección de Comprobantes: A diferencia del módulo de Ventas, en Compras no se respetará el campo `estado`. Todos los tipos de comprobantes estarán disponibles para ser seleccionados. Se implementará una consulta/buscador integrado que permita localizar el comprobante escribiendo indistintamente su código numérico o su descripción.


### 4. Reglas de Negocio e Integridad Transaccional
Integridad de Stock: Toda actualización de existencias (bienes de cambio, insumos, gasoil) debe dispararse exclusivamente vía signals desde los movimientos de Compras/Ventas, garantizando la consistencia ante reversiones.
Determinación Contable: Uso mandatorio de cli_pro.cta_pat para la contrapartida patrimonial. Las órdenes de pago y recibos en Tesorería deben liquidar las cuentas pendientes generadas en estos módulos.


## V. ESPECIFICACIÓN DE REQUERIMIENTOS FUNCIONALES (COBROS Y PAGOS)

### 1. Cobros (Tesorería)
Tipos de Cobranza:
Con imputación: Permite la aplicación total o parcial de saldos pendientes de facturas de venta.
Sin imputación: Para conceptos como aportes de propietarios.
Imputación: Puede realizarse al momento de la cobranza o posteriormente mediante un formulario específico.
Medios de Cobro: Efectivo, transferencia, valores de terceros (cheques), tarjetas de crédito/débito y moneda extranjera (dólares, euros).
Gestión de Moneda Extranjera:
El recibo permite definir la moneda (pesos, dólar, euro).
Si es pesos, cotización = 1. Si es extranjera, se registra el tipo de cambio.
Contabilidad: Todas las registraciones se realizan en pesos (monto extranjero * cotización). La leyenda del movimiento (asto_mov) hará referencia a la moneda extranjera y su tipo de cambio.
Estructura de tablas: recibo contendrá el campo dolar (monto moneda extranjera) y cotiz (cotización).
Tablas de Respaldo:
tarjetas_mov: Vinculación con recibo mediante asiento_id. Campos: recibo_id, lote, cupon, tarjeta_id.
valores_terceros: Trazabilidad mediante asto_cobro y asto_pago. Campos: vencimiento, banco_girado, cuit_librador, razon_social_librador, importe.
Transferencias: En ausencia de comprobante, se obtienen del resumen bancario para la conciliación.

### 2. Pagos (Tesorería)
Tipos de Pago:
Con imputación: Pago de facturas a proveedores.
Sin imputación: Depósitos bancarios, retiros de socios, gastos menores, fondos a rendir.
Medios de Pago: Efectivo, transferencia, cheques propios (tabla cheques con fecha vencimiento y número), valores de terceros (vía asto_pago), tarjetas corporativas y moneda extranjera.
Retenciones: La orden de pago debe gestionar la retención del impuesto a las ganancias.
Gestión de Moneda Extranjera:
Misma lógica de pesificación y cotización que en Cobros.
Si el comprobante es en moneda extranjera y el pago en pesos, se utiliza la cotización histórica guardada en la factura de compra.
Integración: Todos los eventos deben integrarse mediante asiento_id, siguiendo la lógica centralizada de los sistemas "BALANCES" y "COMERCIO_SAS".
