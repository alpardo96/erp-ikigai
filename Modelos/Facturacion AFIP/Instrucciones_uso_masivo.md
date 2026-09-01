# Instrucciones de Uso: Facturación Masiva

El script `script_facturacion_masiva.py` está diseñado para procesar archivos de Excel (`.xlsx`) o CSV con una gran cantidad de facturas (ej. 25.000 filas) de manera segura y eficiente.

A diferencia del script estándar, esta versión:
1. **Agrupa en lotes (chunks):** Envia hasta 100 facturas por petición a AFIP en lugar de 1 en 1, lo que divide el tiempo total de procesamiento drásticamente.
2. **Guarda en vivo:** Guarda los resultados en el archivo `.csv` de salida inmediatamente después de procesar cada lote, para evitar pérdidas de datos en caso de corte de luz o caída de internet.
3. **Reintentos Automáticos:** Si hay un microcorte, pausará y volverá a intentar conectarse con AFIP automáticamente.

## ⚠️ Regla de Oro para el Archivo Excel/CSV de Entrada

Para que AFIP acepte enviar un "Lote" de facturas en una sola petición, **todas las facturas de ese lote deben compartir el mismo Punto de Venta (`pto_vta`) y el mismo Tipo de Comprobante (`cbte_tipo`)**.

Aunque el script intentará ordenar y agrupar automáticamente tu archivo antes de procesarlo, **la recomendación oficial para evitar sorpresas o errores de memoria es que ordenes tu archivo de origen antes de ejecutar el script**:

1. Abre tu Excel.
2. Ordena toda la tabla primero por la columna `pto_vta`.
3. Y luego (secundariamente) por la columna `cbte_tipo`.
4. Guarda el archivo como `plantilla_facturacion.xlsx` o `.csv`.

Al hacer esto, el script detectará automáticamente cuándo cambia el punto de venta y cortará el lote, enviándolo a AFIP, para luego empezar un lote nuevo con el siguiente punto de venta.

## ¿Qué pasa si el script se interrumpe a la mitad?

Si por alguna razón de fuerza mayor el script se detiene (ej. a las 15.000 facturas de 25.000):
1. No perderás el progreso. El archivo `facturacion_masiva_YYYYMMDD.csv` ya tendrá las 15.000 facturas aprobadas con su CAE.
2. Para continuar, **debes eliminar manualmente** esas 15.000 filas que ya fueron aprobadas de tu `plantilla_facturacion.xlsx` original.
3. Vuelve a ejecutar el script con las 10.000 restantes. 
*(No ejecutes el archivo original completo nuevamente, porque AFIP rechazará las que ya se facturaron o podrías duplicar operaciones si no le pasaste los datos exactos).*

## Ejecución

El proceso de ejecución es idéntico al original:
- Coloca tus certificados en `certificados/` y tu CUIT en `cuitemisor.txt`.
- Asegúrate de que `confg.PROD = False` si estás probando, o `True` si ya estás en producción.
- Corre el script:
  ```bash
  python script_facturacion_masiva.py
  ```
- Espera a que termine. Podrás ver en la pantalla el progreso lote por lote.

## Diccionario de Campos (Plantilla CSV/Excel)

Basado en la [documentación oficial de AFIP (WSFEv1)](https://www.afip.gob.ar/fe/ayuda/documentos/wsfev1-RG-4291.pdf), aquí tienes el significado de cada campo que debe ir como columna en tu Excel/CSV:

### Campos Obligatorios Generales
*   **`id_interno`**: Identificador único tuyo (ej. un ID de tu sistema o número correlativo). El script lo usa para que puedas identificar qué fila falló o se aprobó. No va a AFIP.
*   **`pto_vta`**: (Numérico) Punto de Venta configurado para Web Services (ej: `1`, `2`).
*   **`cbte_tipo`**: (Numérico) Código del tipo de comprobante. Ejemplos comunes:
    *   `1`: Factura A | `2`: Nota Débito A | `3`: Nota Crédito A
    *   `6`: Factura B | `7`: Nota Débito B | `8`: Nota Crédito B
    *   `11`: Factura C | `12`: Nota Débito C | `13`: Nota Crédito C
*   **`concepto`**: (Numérico) Lo que estás facturando: `1` (Productos), `2` (Servicios), `3` (Productos y Servicios).
*   **`doc_tipo`**: (Numérico) Tipo de documento del receptor. Ej: `80` (CUIT), `96` (DNI), `99` (Sin identificar / Consumidor Final).
*   **`doc_nro`**: (Numérico) Número de CUIT o DNI del receptor. Si el tipo es `99`, va `0`. Idealmente **sin guiones ni espacios** (ej: `20123456789`), aunque el script los limpiará automáticamente si se te escapan.
*   **`cbte_fch`**: (Formato `AAAAMMDD`) Fecha del comprobante. Ej: `20231024`.

### Importes (Usar punto para decimales)
*   **`imp_total`**: Importe total del comprobante. Debe ser la suma exacta de: *Neto + IVA + Tributos + Exentos + No Gravados*.
*   **`imp_neto`**: Importe neto gravado (el subtotal sobre el que se calcula el IVA). Si es Factura C o Exento, va `0`.
*   **`imp_iva`**: Importe total del impuesto IVA.
*   **`imp_tot_conc`**: Importe total de conceptos No Gravados.
*   **`imp_op_ex`**: Importe total de operaciones Exentas.
*   **`imp_trib`**: Importe total de otros Tributos (percepciones, impuestos internos, etc.).

### Condición IVA Receptor (RG 5616)
*   **`condicion_iva_receptor_id`**: (Numérico) Obligatorio por la RG 5616. Indica la condición frente al IVA del cliente/receptor. Variantes admitidas:
    *   `1`: IVA Responsable Inscripto
    *   `2`: IVA Responsable No Inscripto
    *   `3`: IVA No Responsable
    *   `4`: IVA Sujeto Exento
    *   `5`: Consumidor Final
    *   `6`: Responsable Monotributo
    *   `7`: Sujeto No Categorizado
    *   `8`: Proveedor del Exterior
    *   `9`: Cliente del Exterior
    *   `10`: IVA Liberado - Ley Nº 19.640
    *   `11`: IVA Responsable Inscripto - Agente de Percepción
    *   `13`: Monotributista Social
    *   `14`: Pequeño Contribuyente Eventual Social

### Campos Específicos de Servicios (Obligatorios si concepto es 2 o 3)
*   **`fch_serv_desde`**: (Formato `AAAAMMDD`) Fecha de inicio del servicio.
*   **`fch_serv_hasta`**: (Formato `AAAAMMDD`) Fecha de fin del servicio.
*   **`fch_vto_pago`**: (Formato `AAAAMMDD`) Fecha de vencimiento para el pago.

### Campos Específicos para IVA (Obligatorios si imp_iva > 0)
*   **`id_iva`**: (Numérico) Código de la alícuota de IVA. Ej: `3` (0%), `4` (10.5%), `5` (21%), `6` (27%).
*   **`base_imp`**: Importe base sobre el que se calculó esa alícuota (suele coincidir con `imp_neto`).

### Campos para Notas de Crédito / Débito (Comprobante Asociado)
Si estás emitiendo una Nota de Crédito o Débito (ej. cbte_tipo 3, 8, 13), es obligatorio indicar qué factura estás anulando o modificando:
*   **`cbte_asoc_tipo`**: El tipo del comprobante original (ej: `1` si vas a anular una Factura A).
*   **`cbte_asoc_pto_vta`**: El punto de venta del comprobante original.
*   **`cbte_asoc_nro`**: El número exacto del comprobante original.
