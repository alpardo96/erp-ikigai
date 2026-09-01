Integrar el Web Service de ARCA (WSFEv1) para la obtención del CAE en tiempo real, garantizando la integridad contable y transaccional del ERP. Se implementa un patrón de "Commit de Dos Fases" y un "Bucle de Reintento" para evitar el colapso de la base de datos por latencia externa y mitigar colisiones de concurrencia al delegar la numeración al fisco.

## 1. Análisis Contable y Arquitectónico

* **Aislamiento de Presupuestos:** La conexión a AFIP se disparará **exclusivamente** cuando la venta tenga `condic = 1` (Fiscal). Las operaciones con `condic = 2` (Presupuesto X) seguirán su flujo interno de numeración sin tocar el Web Service.


* **Transaccionalidad (Two-Phase):** La llamada HTTP a AFIP debe ocurrir **fuera** del bloque `transaction.atomic()`. Solo si AFIP responde con éxito y otorga el CAE, se abre la transacción de base de datos para guardar la cabecera, descontar el stock y generar el asiento contable.


* **Delegación de Numeración:** Dado que el 25/07/2026 eliminamos el campo "Número" de la UI, será AFIP quien dicte el número asignado (`CbteDesde`), el cual inyectaremos en el modelo `Venta` justo antes de guardar.



## 2. Modelos (Impacto en Base de Datos)

| Modelo | App | Campos clave a agregar / modificar | Notas |
| --- | --- | --- | --- |
| `Venta` | `facturacion` | `cae` (CharField 20, null), `vto_cae` (DateField, null), `qr_afip` (TextField, null) | Alojarán la respuesta de AFIP. |
| `Empresa` | `empresas` | `cuit` (CharField 11), `crt_afip` (FileField), `key_afip` (FileField) | Reemplaza la lectura de certificados locales por variables de base de datos por inquilino. |

## 3. Servicios

| Servicio | Archivo | Firma | Qué hace |
| --- | --- | --- | --- |
| AFIP Service | `facturacion/services/afip_service.py` | `emitir_factura_con_reintento(...)` | Encapsula el `script_facturacion.py`. Arma el payload con los datos en memoria, consulta el WSFE con límite de 3 reintentos ante colisión de números, y devuelve un diccionario con éxito/CAE/error. |
| Notas Crédito | `facturacion/services/notas_credito.py` | Modificar emisión de NC | Si el comprobante original es `condic=1`, debe inyectar la matriz `CbtesAsoc` con los datos de la factura padre hacia el servicio de AFIP antes de guardar.

 |

## 4. Archivos a Crear/Modificar

* `empresas/models.py` — Agregar campos de CUIT y certificados al modelo `Empresa`.
* `facturacion/models.py` — Agregar campos CAE, Vencimiento y QR al modelo `Venta`.
* `facturacion/services/afip_service.py` — Crear servicio transaccional externo (adaptación del script del usuario).
* `facturacion/views.py` — Modificar `VentasCargaView.post` para ejecutar la Fase 1 (AFIP) y Fase 2 (BD). Modificar `VentaAnularModalView` para pasar parámetros vinculantes en devoluciones.


* `templates/facturacion/ventas_carga.html` — Inyectar `hx-disabled-elt="this"` y `hx-indicator="#spinner-afip"` al botón de guardado para evitar concurrencia visual por impaciencia del usuario.



## 5. Tests Mínimos

| Test | Qué verifica |
| --- | --- |
| `test_afip_exito_guarda_datos` | Simula una respuesta OK de AFIP y verifica que la Venta se guarda con stock y asiento. |
| `test_afip_error_rechaza_transaccion` | Simula un rechazo de AFIP y verifica que NO se guarda la Venta, NO baja el stock y NO se genera asiento. |
| `test_condic_2_no_llama_afip` | Verifica que las ventas de `condic=2` se guardan directamente sin invocar el mock de AFIP. |

## 6. Dependencias y Riesgos

* **Requiere:** Módulo de Puntos de Venta (`PuntoVenta`) finalizado el 23/07/2026 para asociar correctamente la factura.


* **Riesgo Mitigado:** La latencia de AFIP podría causar *Lock Contention*. Solucionado ejecutando AFIP antes de `transaction.atomic()`.
* **Riesgo Mitigado:** Al anular ventas desde el listado, AFIP exige comprobantes asociados para NC. Solucionado mediante inyección de contexto desde `VentaAnularModalView`.



## 7. Criterio de Hecho

* [ ] La base de datos tiene los campos CAE en `Venta`.
* [ ] Si AFIP cae o rechaza, el sistema devuelve una alerta visual roja en HTMX y no asienta nada en base de datos.
* [ ] Si AFIP aprueba, el sistema guarda la venta, descuenta stock, genera el asiento y muestra el CAE en el comprobante.


* [ ] Las anulaciones de comprobantes fiscales generan Notas de Crédito autorizadas por AFIP conectadas a la factura original.

---