# Plan 019 — Módulo de Preventa y Autorizaciones

## Objetivo
Implementar la arquitectura para la carga de Preventas, gestión de descuentos máximos a nivel Rubro y el flujo de autorizaciones a nivel de comprobante.

## Decisiones y Criterios Aprobados
1. **Autorización a nivel comprobante:** La preventa entera entra en estado "Pendiente de Autorización" si algún ítem supera el descuento máximo permitido de su rubro.
2. **Modelos Independientes:** Se crean `Preventa` y `PreventaItem` separados de `Venta`.
3. **Límite de Descuento:** El porcentaje máximo autorizado se define en el modelo `Rubro`.
4. **Notificaciones:** Se implementará una "Bandeja de Autorizaciones" para los responsables.
5. **Restricción Armería:** Si la empresa es de rubro Armería, se visualizará el vencimiento del CLU del cliente durante la carga de la preventa, permitiendo su actualización si estuviera vencido.

## Cambios en Modelos

- **`empresas/models.py`**: Agregar `es_armeria` (Boolean) en `Empresa`.
- **`productos/models.py`**: Agregar `descuento_maximo` (DecimalField) en `Rubro`.
- **`usuarios/models.py`**: Agregar `permiso_autorizar_descuentos` en `Perfil`.
- **`facturacion/models.py`**:
  - `Preventa`: `cliente`, `vendedor`, `fecha`, `empresa`, `sucursal`, `estado` (choices: Borrador, Pendiente Autorización, Autorizada, Facturada, Anulada), `total`.
  - `PreventaItem`: `preventa`, `producto`, `cantidad`, `precio_unitario`, `porcentaje_descuento`, `total`.

## Flujo de Vistas (HTMX)
- Formulario Cabecera Preventa (selección cliente, carga vendedor predeterminado).
- Validación de CLU (si empresa es armería).
- Interfaz dinámica de Ítems (validación de descuentos contra rubro).
- Cierre de Preventa y evaluación de estados.
- Bandeja de Autorizaciones para responsables.
