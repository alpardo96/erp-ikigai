# Facturación con Tributos Múltiples (Percepciones)

Esta versión de los scripts (`script_facturacion_tributos.py` y `script_facturacion_masiva_tributos.py`) soporta el envío de hasta 3 tributos o percepciones simultáneas (por ejemplo, Percepción de IVA y Percepción de Ingresos Brutos) en un mismo comprobante.

## ¿Qué cambió en la plantilla?
La nueva plantilla `plantilla_facturacion_tributos.csv` (o `.xlsx`) ignora la antigua columna `imp_trib`. En su lugar, al final de la planilla, cuenta con 15 columnas nuevas agrupadas de a 5 (Tributo 1, Tributo 2 y Tributo 3):

Por cada tributo debes llenar:
- **`tribX_id`**: Código de AFIP del impuesto.
  - `1`: Impuestos Nacionales (Acá va la **Percepción de IVA**)
  - `2`: Impuestos Provinciales (Acá va **Percepción de Ingresos Brutos**)
  - `3`: Impuestos Municipales
  - `4`: Impuestos Internos
  - `99`: Otros
- **`tribX_desc`**: Descripción para que aparezca en el comprobante (Ej: "Percepcion IVA" o "Perc IIBB ARBA").
- **`tribX_base`**: Base Imponible sobre la que se calcula la retención (en formato numérico, ej: 1000.50).
- **`tribX_alic`**: Porcentaje de la alícuota cobrada (ej: 3.0).
- **`tribX_importe`**: Monto final retenido (en pesos).

### Cálculo Automático
- No necesitas completar a mano la antigua columna `imp_trib` ni sumar los tributos al `imp_total`.
- El script calculará y sumará automáticamente el importe de los tributos que hayas llenado para que los totales enviados a AFIP sean matemáticamente perfectos.

## ¿Qué pasa si tengo solo 1 tributo?
Si tu factura solo tiene Percepción de IVA (1 solo tributo), simplemente llena las columnas correspondientes al tributo 1 (`trib1_id`, `trib1_desc`, etc.) y **deja las columnas de los tributos 2 y 3 completamente en blanco (vacías)**. El script las omitirá automáticamente.

## ¿Cómo ejecuto esta versión?
Usa esta versión abriendo una consola y ejecutando:
`python script_facturacion_tributos.py` o `python script_facturacion_masiva_tributos.py` en lugar de los scripts habituales.
