# Plan Integral de Mapeo de Tablas Legacy (VFP) a PostgreSQL - V7

## Contexto y Directivas Clave
**Regla de Oro:** La carpeta `eje_272` representa exactamente **1 Empresa** y **1 Ejercicio Contable**. Todo el lote de datos se inyectará apuntando de forma fija y constante a esa misma empresa y ejercicio en Django. **No debe sobrar ni faltar ningún dato**.

## 0. Creación de Entorno Base (Manual o Inicialización)
Antes de correr los scripts, estas 4 entidades deben existir en Django para anclar toda la migración:
1. **`Empresa`** (id=1): Los 384 clientes, 6738 asientos y demás tablas apuntarán a ella (`empresa_id = 1`).
2. **`Ejercicio`** (id=1): Se tomará de `vinculadas.dbf` (1 registro). Todos los asientos y facturas apuntarán aquí (`ejercicio_id = 1`).
3. **`Sucursal`** (id=1): Requisito estructural de Django. (`sucursal_id = 1`).
4. **`Usuario`** (id=1): Usuario "Migrador" para satisfacer los campos `usuario_id` requeridos por auditoría.
5. **`Caja`** (id=1, Tipo 'T'): Requisito para poder inyectar la Caja Diaria (`caja_id = 1`).

---

## Bloque 1: Maestros y Parámetros Base

| FoxPro (.dbf) | Registros | Modelo Django Destino | Lógica de Mapeo |
| :--- | :---: | :--- | :--- |
| `cli_pro.dbf` | 384 | `ClienteProveedor` | Inyección Directa (`CODIGO` ➡️ `codigo_id`). |
| `cuentas.dbf` | 247 | `Cuenta` | Inyección Directa (`CODIGO` ➡️ `id`). `tipo` se deduce del 1° dígito de la jerarquía. |
| `parametros_contables.dbf`| 1 | `ParametrosContables` | Cruce directo de las cuentas maestras de caja, iva, retenciones. |
| `condic_iva.dbf` | 4 | *No aplica (Diccionario)* | Se usa en memoria para mapear el `INSC_IVA` de `cli_pro` a los choices (ej. 'RESPONSABLE INSCRIPTO'). |
| `alicuotas_iva.dbf` | 6 | `AlicuotaIva` | Inyección Directa (`COD_ALIC` ➡️ `codigo`, `ALICUOTA` ➡️ `porcentaje`). |
| `provincias.dbf` | 24 | `Jurisdiccion` | Inyección Directa (`CODIGO` ➡️ PK, `DETALLE` ➡️ `nombre`). |
| `comprobantes.dbf` | 23 | `TipoComprobante` | Inyección Directa. Los códigos de 2 letras (FA, CB) cruzan contra la FK `tipo_id` en Venta/Compra. |

---

## Bloque 2: Contabilidad Core

| FoxPro (.dbf) | Registros | Modelo Django Destino | Lógica de Mapeo |
| :--- | :---: | :--- | :--- |
| `asto_enc.dbf` | 6,738 | `Asiento` | `ASIENTO` ➡️ `asiento_id`. Se fija `empresa_id=1`, `ejercicio_id=1`, `sucursal_id=1`. |
| `asto_mov.dbf` | 17,042 | `AsientoLinea` | FK directo al `asiento_id`. Los campos `DEBE` y `HABER` cruzan sin cambios. |
| `apertura.dbf` | 68 | `Asiento` / `AsientoLinea` | Son los saldos iniciales. Se genera un único Asiento (con `condic=3` Apertura) y 68 líneas. |
| `vinculadas.dbf` | 1 | `Ejercicio` | De aquí se extraen las fechas de inicio y cierre del ejercicio para crear el `ejercicio_id=1`. |

---

## Bloque 3: Facturación y Libro IVA

| FoxPro (.dbf) | Registros | Modelo Django Destino | Lógica de Mapeo |
| :--- | :---: | :--- | :--- |
| `lib_iva.dbf` | 2,681 | `Compra` / `Venta` | Si `C_V = 'C'` va a `Compra`. Si `C_V = 'V'` va a `Venta`. Se mapea `ID_ASTO` ➡️ `asiento_id`. |
| `lib_iva_afip.dbf`| 677 | `Venta` (Update) | Contiene los **CAE**. Se hace un UPDATE sobre las ventas generadas previamente utilizando el `ID_ASTO` como pivote para setear `cae`. |
| `lib_iva_alic.dbf`| 1,226 | `LibroIvaAlic` | Desglose del IVA. Cruza directo por `ID_ASTO`. |
| `rg_380_retenciones.dbf`| 2 | `RetencionPracticada` | Retenciones efectuadas en pagos. |

---

## Bloque 4: Tesorería (Cajas, Bancos, Cobros y Pagos)

| FoxPro (.dbf) | Registros | Modelo Django Destino | Lógica de Mapeo |
| :--- | :---: | :--- | :--- |
| `enc_caja_diaria.dbf` | 288 | `CajaSesion` | Cada registro es un "turno" de caja. Se fuerza `caja_id=1` y `usuario_id=1`. |
| `caja_diaria.dbf` | 3,797 | `MovimientoCaja` | Movimientos individuales en efectivo. FK hacia la `CajaSesion`. |
| `bancos.dbf` | 82 | `Banco` | Maestro general de bancos. |
| `cta_cte.dbf` | 3 | `CuentaBancaria` | Las 3 cuentas bancarias de la empresa. Se asocian al banco correspondiente. |
| `recibos.dbf` | 1,696 | `Recibo` | Cabecera de los recibos de cobranza a clientes. |
| `ord_pago.dbf` | 2,302 | `OrdenPago` | Cabecera de los pagos a proveedores. |
| `ord_pago_facturas.dbf`| 2,226 | `OrdenPagoAplicacion` | Define qué facturas canceló cada orden de pago. **Fundamental para los saldos corrientes**. |
| `valores_terceros.dbf` | 1,049 | `ValorTerceros` | Cheques de clientes en cartera. |
| `cheques.dbf` | 366 | `TransaccionBancaria` | Cheques propios emitidos. Se inyectan con tipo `'CP'` (Cheque Propio). |
| `tarjetas.dbf` | 5 | `Tarjeta` | Maestro de tarjetas. |
| `tarjetas_mov.dbf`| 209 | `CobroTarjeta` | Cupones cobrados con tarjeta. |

---

## Bloque 5: Tablas Vacías o No Aplicables (Se Ignoran)
Tablas que vinieron en la base de datos pero que **no contienen registros** o son de módulos discontinuados:
- `balance.dbf` (0 reg)
- `chequeras.dbf` (0 reg)
- `ret_per_iibb.dbf` (0 reg)
- `liquidacion_tarjetas.dbf` (0 reg)
- `conceptos_devengado.dbf` (0 reg)
- `devengado_enc.dbf` (13 reg) y `devengado_mov.dbf` (79 reg) → *Módulo de facturación recurrente legado que no tiene equivalente nativo en los modelos mostrados, se recomienda obviar a menos que requieras migrarlos como ventas estándar*.
- `centro_costos.dbf` (13 reg) → *Django no tiene un modelo de Centro de Costos implementado en la app contable actual*.
- `conceptos_bcarios.dbf` (167 reg) → *Diccionario obsoleto, los conceptos bancarios en Django se manejan imputando directamente a las Cuentas*.
- `iva_cierre.dbf` (4 reg) → *Tabla de control interno del legacy sin tabla destino*.
- `t_cli_pro.dbf` (12 reg) → *Etiquetas de clientes del legacy sin equivalente*.
