# Facturación Electrónica ARCA (AFIP)

## Estructura de la carpeta

```
FacturacionARCA/
├── FacturacionARCA.exe          ← Ejecutable principal
├── plantilla_facturacion.csv    ← Archivo con los datos a facturar
├── certificados/                ← Carpeta con tus certificados
│   ├── tu_archivo.key           ← Clave privada (cualquier nombre, extensión .key)
│   └── tu_archivo.crt           ← Certificado (cualquier nombre, extensión .crt)
└── facturacion_YYYYMMDD.csv     ← Resultado generado (fecha del día)
    facturacion_YYYYMMDD.xlsx    ← Resultado en Excel (fecha del día)
```

## Cómo usar

1. **Colocá tus certificados** en la carpeta `certificados/`:

   - Un archivo `.key` (clave privada)
   - Un archivo `.crt` (certificado)
   - Los nombres no importan, el programa los detecta automáticamente por extensión.
2. **Completá la plantilla** `plantilla_facturacion.csv` con los datos de las facturas a emitir.
3. **Ejecutá** `FacturacionARCA.exe` (doble clic).
4. **Revisá los resultados** en los archivos generados:

   - `facturacion_YYYYMMDD.csv` → Para importar en otros sistemas.
   - `facturacion_YYYYMMDD.xlsx` → Para revisar en Excel con formato y colores.

## Columnas de la plantilla CSV

| Columna        | Descripción                                                           |
| -------------- | --------------------------------------------------------------------- |
| `id_interno`   | Identificador interno (libre, para tu referencia)                     |
| `pto_vta`      | Punto de venta                                                        |
| `cbte_tipo`    | Tipo de comprobante (ej: 6=Factura B, 1=Factura A, 8=Nota Débito B)   |
| `concepto`     | 1=Productos, 2=Servicios, 3=Productos y Servicios                     |
| `doc_tipo`     | Tipo de documento del receptor (80=CUIT, 96=DNI, 99=Consumidor Final) |
| `doc_nro`      | Número de documento del receptor                                      |
| `cbte_fch`     | Fecha del comprobante (formato YYYYMMDD)                              |
| `imp_total`    | Importe total del comprobante                                         |
| `imp_neto`     | Importe neto gravado                                                  |
| `imp_iva`      | Importe de IVA                                                        |
| `imp_op_ex`    | Importe operaciones exentas                                           |
| `imp_tot_conc` | Importe total no gravado                                              |
| `imp_trib`     | Importe de tributos                                                   |
| `id_iva`       | ID de alícuota IVA (5=21%, 4=10.5%, 6=27%)                            |
| `base_imp`     | Base imponible del IVA                                                |