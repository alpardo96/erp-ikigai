# Plan 061: Establecer Fecha Actual por Defecto en Filtros Desde/Hasta (Recibos, Órdenes de Pago, Compras y Ventas)

Fecha: 2026-08-21
Objetivo: Optimizar los tiempos de respuesta y carga inicial de los listados de comprobantes de Tesorería (Recibos y Órdenes de Pago) y Facturación (Compras y Ventas), estableciendo por defecto la fecha actual (`hoy`) en los filtros `desde` y `hasta` cuando la vista no recibe dichos parámetros en la petición GET.

## Análisis de Impacto y Archivos a Modificar

1. **Tesorería (`tesoreria/views_listados.py`)**
   - Función `_rango_fechas(request)`:
     - Cambiar `desde = request.GET.get('desde') or hoy.replace(day=1).isoformat()` por `desde = request.GET.get('desde') or hoy.isoformat()`.
     - Impacta de forma directa e integral en:
       - Listado de Recibos (`recibos_listado` / `recibos_grilla`)
       - Listado de Órdenes de Pago (`ordenes_pago_listado` / `ordenes_pago_grilla`)

2. **Facturación (`facturacion/views.py`)**
   - Vista `ComprasListView.get`:
     - Configurar `desde` y `hasta` por defecto con la fecha de hoy (`timezone.localdate().isoformat()`) cuando no se pasen por parámetro GET.
   - Vista `VentasListView.get`:
     - Configurar `desde` y `hasta` por defecto con la fecha de hoy (`timezone.localdate().isoformat()`) cuando no se pasen por parámetro GET.

## Plan de Pruebas

- Pruebas automatizadas de vistas en `tesoreria.tests` y `facturacion.tests`.
- Verificación manual navegando por `/tesoreria/recibos/`, `/tesoreria/ordenes-pago/`, `/facturacion/compras/` y `/facturacion/ventas/`.
