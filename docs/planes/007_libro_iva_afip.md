# Plan 007 — Libro IVA Digital + AFIP CAE

## Estado: ❌ Pendiente

## Objetivo
Implementar el Libro IVA Digital (RG 5616) derivado de compras/ventas validadas, la integración con AFIP para solicitud de CAE (factura electrónica), y la importación de libro IVA desde Excel/PDF.

## Modelos

| Modelo | App | Campos clave | Notas |
|--------|-----|-------------|-------|
| `AlicuotaIva` | `facturacion` | FK compra/venta, `alicuota` (0/2.5/5/10.5/21/27), `neto`, `iva` | Alícuotas múltiples por comprobante |
| `CertificadoAfip` | `empresas` | FK empresa, `pfx_file`/`key_file`/`crt_file`, `password_cifrada`, `ambiente` (homo/prod) | Password cifrada con Fernet |

## Servicios

| Servicio | Archivo | Firma | Qué hace |
|----------|---------|-------|----------|
| Exportar Libro IVA | `facturacion/services/libro_iva.py` | `exportar_aplicativo_afip(empresa, periodo)` | Genera TXT formato RG 5616 |
| Solicitar CAE | `facturacion/services/afip/wsfev1.py` | `solicitar_cae(venta)` | WSAA + WSFEv1 → asigna CAE |
| Auth WSAA | `facturacion/services/afip/wsaa.py` | `autenticar(empresa)` | Token/Sign con cryptography |
| QR Factura | `facturacion/services/afip/qr.py` | `generar_qr(venta)` | QR según spec AFIP |
| Import Excel | `facturacion/management/commands/importar_libro_iva.py` | `--empresa --periodo --archivo` | Importa libro IVA desde XLS |

## Archivos a Crear/Modificar
- `facturacion/models.py` — agregar `AlicuotaIva`
- `empresas/models.py` — agregar `CertificadoAfip`
- `facturacion/services/libro_iva.py` — exportación RG 5616
- `facturacion/services/afip/` — paquete con `wsaa.py`, `wsfev1.py`, `qr.py`
- `facturacion/management/commands/importar_libro_iva.py`

## Tests Mínimos

| Test | Qué verifica |
|------|-------------|
| `test_alicuotas_multiples` | Comprobante con 21% + 10.5% genera 2 registros de AlicuotaIva |
| `test_exportar_libro_iva_formato` | El TXT generado cumple formato RG 5616 |
| `test_solicitar_cae_mock` | Mock WSAA/WSFEv1, validar parsing de respuesta |
| `test_certificado_password_cifrada` | Password se almacena cifrada y se descifra correctamente |

## Dependencias
- Requiere: `facturacion` ✅, `contable` ✅

## Referencia VFP
- DBFs: `lib_iva.dbf`, `aux_lib_iva_afip_c.dbf`, `aux_lib_iva_afip_v.dbf`
- PRGs: `carga_libro_iva_xls.prg`, `contabiliza_libro_iva.prg`, `afip_autorizacion.prg`
- Doc: `Facturacion Electronica ARCA.md` (formato CSV de FacturacionARCA.exe)

## Criterio de Hecho
- [ ] Libro IVA se obtiene desde comprobantes validados
- [ ] CAE se solicita y almacena correctamente (al menos en homologación)
- [ ] Import de libro IVA desde Excel funciona
- [ ] Tests pasan
