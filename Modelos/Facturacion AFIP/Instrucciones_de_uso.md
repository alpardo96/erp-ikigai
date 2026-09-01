# Instrucciones de Uso: Facturación Masiva (ARCA / AFIP)

Esta guía explica cómo utilizar la plantilla de facturación para emitir **Facturas A y B** bajo el concepto de **Servicios**.

## 1. Archivo de Plantilla (`plantilla_facturacion.xlsx` o `.csv`)

Deberás usar el archivo de plantilla provisto. La mejor opción es guardarlo y trabajarlo directamente como un archivo de Excel normal (**`plantilla_facturacion.xlsx`**), así no perdés el formato de los números. 
También podés usarlo como `.csv` (el programa ahora detecta automáticamente si Excel lo guardó usando comas o punto y coma).

## 2. Campos Clave para Servicios (Concepto 2)

A continuación se detalla qué poner en cada columna para emitir correctamente Facturas A y B de Servicios:

- **`concepto`**: Para servicios, este valor **siempre debe ser `2`**.
- **`cbte_tipo`**: 
  - `1` = Factura A (Requiere que el cliente sea un CUIT válido).
  - `6` = Factura B (Consumidor Final o IVA Exento).
  - `3` = Nota de Crédito A.
  - `8` = Nota de Crédito B.
- **`doc_tipo`**: Tipo de documento del cliente.
  - `80` = CUIT (Obligatorio para Facturas A).
  - `96` = DNI (Común en Facturas B).
  - `99` = Consumidor Final (Sin identificación, `doc_nro` debe ser `0`).
- **`doc_nro`**: El número de CUIT o DNI del cliente (sin guiones).
- **Fechas**: **Todas las fechas** deben tener el formato `AAAAMMDD` (Ejemplo: `20260701` para el 1 de julio de 2026).
  - **`cbte_fch`**: Fecha de emisión de la factura.
  - **`fch_serv_desde`**: Inicio del período facturado del servicio. (Ej: `20260701`)
  - **`fch_serv_hasta`**: Fin del período facturado del servicio. (Ej: `20260731`)
  - **`fch_vto_pago`**: Fecha de vencimiento para el pago de la factura. (Ej: `20260810`)
  
> [!IMPORTANT]
> Las columnas `fch_serv_desde`, `fch_serv_hasta` y `fch_vto_pago` son **OBLIGATORIAS** para AFIP/ARCA cuando se usa `concepto = 2` (Servicios).

## 3. Importes e IVA

Los importes deben escribirse usando **punto** como separador decimal (ej: `10000.50`), **nunca coma**.

- **`imp_neto`**: Importe sin IVA. (Ej: `10000`)
- **`imp_iva`**: Monto total del IVA. (Ej: `2100`)
- **`imp_total`**: Suma de `imp_neto` + `imp_iva`. (Ej: `12100`)
- **`id_iva`**: Código de la alícuota de IVA aplicable.
  - `3` = 0%
  - `4` = 10.5%
  - `5` = 21%
  - `6` = 27%
  - `8` = 5%
  - `9` = 2.5%
- **`base_imp`**: Igual al `imp_neto`.
- **`condicion_iva_receptor_id`** (RG 5616): Obligatorio. Indica la condición de IVA del cliente.
  - `1` = IVA Responsable Inscripto  A necesita CUIT
  - `2` = IVA Responsable No Inscripto
  - `3` = IVA No Responsable
  - `4` = IVA Sujeto Exento  B CUIT
  - `5` = Consumidor Final B
  - `6` = Responsable Monotributo A o B CUIT
  - `7` = Sujeto No Categorizado
  - `8` = Proveedor del Exterior
  - `9` = Cliente del Exterior
  - `10` = IVA Liberado - Ley Nº 19.640
  - `11` = IVA Responsable Inscripto - Agente de Percepción
  - `13` = Monotributista Social
  - `14` = Pequeño Contribuyente Eventual Social

## 4. Notas de Crédito / Débito (Opcional)

Si estás emitiendo una Nota de Crédito (`cbte_tipo` 3 u 8), debes completar obligatoriamente las columnas asociadas a la factura original que estás anulando/corrigiendo:
- **`cbte_asoc_tipo`**: Tipo de la factura original (Ej: `1` para Factura A).
- **`cbte_asoc_pto_vta`**: Punto de venta de la factura original.
- **`cbte_asoc_nro`**: Número de la factura original.

## 5. Ejecución

1. Completa el archivo `plantilla_facturacion.csv` asegurándote de no dejar columnas en blanco obligatorias.
2. Haz doble clic en el programa ejecutable.
3. El programa se comunicará con ARCA/AFIP y generará dos archivos nuevos:
   - `facturacion_AAAAMMDD.csv`
   - `facturacion_AAAAMMDD.xlsx` (Recomendado abrir este archivo para ver resultados con colores).
4. Verifica la columna `estado` en el archivo de salida para asegurarte de que diga `FACTURADO` y se haya generado el `cae`.

> [!TIP]
> Si alguna factura fue rechazada, revisa la columna `observaciones` en el Excel generado para entender el motivo del rechazo según ARCA (ej: CUIT inválido, falta fecha de servicio, etc.).
