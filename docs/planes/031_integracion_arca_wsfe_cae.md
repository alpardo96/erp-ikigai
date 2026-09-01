# Plan de Implementación 031: Integración ARCA (WSFEv1), Facturación 1x1 y Discriminación Multi-Alícuota de IVA

**Fecha:** 26 de Julio de 2026  
**Módulo:** Facturación / Productos / Empresas / Configuración  
**Estado:** En revisión para aprobación de Ejecución (Fase 2 - Integración WSFEv1)  

---

## 1. Resumen de Progreso (Fase 1: COMPLETADA ✅)

Hasta la fecha (26/07/2026), se han completado y validado en la base de datos y la interfaz gráfica los pilares fundamentales:
1. **Configuración ARCA por Empresa:** Agregados los campos `crt_afip`, `key_afip` y `entorno_afip` ('HOM' / 'PROD') en el modelo `Empresa` y su interfaz modal (`empresa_form.html`).
2. **Normalización Inteligente de Alícuotas en Producto:** Reestructurado el campo `alic_iva` con `ALICUOTAS_IVA_CHOICES` (`21.00`, `10.50`, `0.00`, `27.00`, `5.00`, `2.50`), propiedades calculadas `alic_iva_porc` e `id_arca_iva` (mapeo a IDs oficiales 3, 4, 5, 6, 8, 9 de AFIP/ARCA) y compatibilidad con migraciones legacy.
3. **Desglose Dinámico en Carrito de Ventas:** Actualizado `ventas_carga.html` y `venta_items_tabla.html` para calcular y mostrar el IVA discriminado por porcentaje y el Total I.V.A. en tiempo real.

---

## 2. Alcance y Objetivos de la Fase 2 (Por Implementar 🚀)

El objetivo de esta fase es conectar el motor de facturación con los servicios web de ARCA (**WSFEv1**) en modalidad **1x1 en tiempo real** (sin lotes masivos), autorizando cada comprobante fiscal emitido por el ERP, obteniendo el **CAE**, la **Fecha de Vencimiento** y el **Código QR oficial**, y persistiendo el desglose impositivo exacto en la base de datos.

---

## 3. Arquitectura Técnica y Cambios Propuestos

### 3.1 Persistencia de Alícuotas Fiscales: `VentaAlicuotaIva` (`facturacion/models.py`)
Para garantizar la trazabilidad fiscal en los reportes de IVA Ventas digital y libros contables, se creará el modelo `VentaAlicuotaIva` vinculado a cada venta:
```python
class VentaAlicuotaIva(models.Model):
    venta = models.ForeignKey('Venta', on_delete=models.CASCADE, related_name='alicuotas_iva')
    id_iva = models.IntegerField(verbose_name="ID Alícuota ARCA")  # 3=0%, 4=10.5%, 5=21%, 6=27%, 8=5%, 9=2.5%
    alicuota = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Porcentaje (%)")
    base_imponible = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    importe_iva = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Alícuota IVA de Venta"
        verbose_name_plural = "Alícuotas IVA de Venta"
```

### 3.2 Adaptador ARCA / WSFEv1: `facturacion/services/afip_service.py`
Se creará el servicio dedicado `afip_service.py` tomando como referencia operativa el motor en `Modelos/Facturacion AFIP/script_facturacion_tributos.py`:
- **Credenciales por Empresa:** Leerá dinámicamente las rutas absolutas de los certificados (.crt y .key) de `Empresa`, su CUIT y el entorno fiscal (`HOM` o `PROD`).
- **Gestión de Autenticación (WSAA):** Generará y manejará temporalmente el Token y Sign de autenticación para no saturar el servidor de autenticación en comprobantes continuos.
- **Estructura del Request (WSFEv1 - `CantReg = 1`):**
  - Construcción automática del array `AlicIva` con todas las alícuotas presentes en la factura:
    ```python
    'Iva': {
        'AlicIva': [
            {
                'Id': int(a['id_iva']),
                'BaseImp': round(float(a['base_imponible']), 2),
                'Importe': round(float(a['importe_iva']), 2)
            }
            for a in alicuotas_list if float(a['base_imponible']) > 0
        ]
    }
    ```
  - Integración del array `Tributos` si la venta posee percepciones o impuestos nacionales/provinciales.
- **Manejo de Reintentos:** En caso de colisión de numeración externa (`FECompUltimoAutorizado`), el adaptador intentará sincronizar el próximo número hasta 3 veces de manera transparente.
- **Respuesta Normalizada:** Devolverá un diccionario con `exito` (bool), `cae`, `vto_cae`, `numero_comprobante`, `cod_qr` o bien el mensaje detallado de rechazo u observación fiscal de ARCA.

### 3.3 Patrón Two-Phase Commit en Carga de Ventas (`facturacion/views.py` - `VentasCargaView.post`)
Para evitar bloqueos de base de datos o inconsistencias ante latencias/fallas de red con ARCA:
1. **Fase Pre-DB (Autorización externa):**
   - Si `condic == 1` (Comprobante Fiscal - Factura/Nota de Crédito/Débito A, B, C, M): se invoca a `afip_service.emitir_comprobante(...)` ANTES de iniciar la transacción local de BD.
   - Si ARCA rechaza el comprobante (ej. CUIT receptor inválido, certificado vencido): el controlador detiene la ejecución y retorna el mensaje de rechazo de ARCA directo a la interfaz del usuario, **sin crear registros huérfanos en BD**.
2. **Fase BD (`with transaction.atomic():`):**
   - Una vez autorizado el CAE y número por ARCA (o en comprobantes internos `condic == 2 - Presupuestos`), se abre la transacción local.
   - Se guarda la cabecera `Venta` (con su CAE, Vto. CAE, y Nro. oficial si es fiscal).
   - Se guardan los ítems `VentaItem`.
   - Se insertan los registros en `VentaAlicuotaIva`.
   - Se ejecuta el descuento de stock y la contabilización del asiento (`contabilizar_venta`).

---

## 4. Plan de Pruebas y Validación

### 4.1 Suite de Tests Unitarios (`facturacion/tests/test_afip_wsfe.py`)
- `test_payload_multi_alicuota`: Verifica que el servicio empaquete correctamente en `AlicIva` ítems combinados al 21% y 10.5% con sus sumas de base imponible e IVA sin errores de redondeo.
- `test_rollback_ante_rechazo_arca`: Simula una respuesta de rechazo por parte del WSFEv1 y valida que no quede ningún registro en `Venta` ni `VentaAlicuotaIva`.
- `test_persistencia_venta_alicuota_iva`: Verifica la inserción en base de datos de los desgloses por alícuota en comprobantes fiscales.

### 4.2 Verificación Operativa en Entorno de Homologación
- Carga manual de una factura A y una factura B en `http://localhost:8000/ventas/carga/` con empresa en entorno 'HOM'.
- Comprobación en pgAdmin de los valores de `cae`, `vto_cae` y `VentaAlicuotaIva`.

---

## 5. Criterios de Aceptación (DoD)
- [ ] La tabla `VentaAlicuotaIva` está migrada y operativa.
- [ ] El servicio `afip_service.py` autentica mediante certificado/clave de Empresa y autoriza comprobantes 1x1 en WSFEv1.
- [ ] Facturas con alícuotas mixtas (21% y 10.5%) o exentas (0%) son procesadas y aceptadas por ARCA sin errores de estructura en `AlicIva`.
- [ ] Rechazos de ARCA no generan impacto en stock, saldos ni contabilidad.
