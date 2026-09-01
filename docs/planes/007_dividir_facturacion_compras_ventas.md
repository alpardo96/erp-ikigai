# Dividir "Facturación" en dos módulos: "Compras" y "Ventas"

## Descripción
Separar el módulo monolítico "Facturación" del sidebar en dos entradas independientes con sus propias rutas URL, páginas index y cards rápidas. También actualizar el SVG de "Contable".

> [!IMPORTANT]
> **No se tocan modelos ni lógica de negocio.** Los cambios son 100% de routing y presentación. El app Django `facturacion` sigue existiendo como unidad de código; solo cambian las URLs y la navegación.

## Estrategia Clave: No Romper Nada

El principio rector es que **los `name=` de las URLs no cambian**. Todas las vistas, `redirect()`, `{% url %}` en templates, y HTMX endpoints siguen usando los mismos nombres (`compras_carga`, `ventas_carga`, `autorizaciones_index`, etc.). Lo único que cambia es el **path URL** de `/facturacion/...` a `/compras/...` o `/ventas/...`.

---

## Cambios Propuestos

### 1. Sidebar en `base.html`

Se reemplaza el bloque desplegable "Facturación" por **dos** bloques desplegables independientes:

#### [MODIFY] [base.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/base.html)

**Bloque "Compras"** (líneas 161-213 aproximadamente):
- SVG: `d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25v10.5A2.25 2.25 0 0 0 4.5 19.5Z"`
- `x-data="{ open: window.location.pathname.startsWith('/compras/') }"`
- Enlace principal → `{% url 'compras_index' %}`
- Sub-ítems: Carga de Compras, Carga Automática, Carga IA, Listado de Compras

**Bloque "Ventas"** (nuevo):
- SVG: El mismo que Facturación actual (calculadora)
- `x-data="{ open: window.location.pathname.startsWith('/ventas/') }"`
- Enlace principal → `{% url 'ventas_index' %}`
- Sub-ítems: Carga de Ventas, Carga de PreVentas, Bandeja Autorizaciones

**Bloque "Contable"** (líneas 248-279):
- Se cambia el SVG del libro abierto:
  `d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"`

---

### 2. URLs en `config/urls.py`

#### [MODIFY] [urls.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/config/urls.py)

Cambios de paths (los `name=` se mantienen idénticos):

| Antes | Después |
|---|---|
| `facturacion/` → `facturacion_index` | **Se elimina** (ya no existe index unificado) |
| (nuevo) | `compras/` → `compras_index` |
| (nuevo) | `ventas/` → `ventas_index` |
| `facturacion/compras/carga/` | `compras/carga/` |
| `facturacion/compras/listado/` | `compras/listado/` |
| `facturacion/compras/<int:compra_id>/baja/` | `compras/<int:compra_id>/baja/` |
| `facturacion/compras/carga-automatica/` | `compras/carga-automatica/` |
| `facturacion/compras/procesar-recorte/` | `compras/procesar-recorte/` |
| `facturacion/compras/carga-ia/` | `compras/carga-ia/` |
| `facturacion/compras/procesar-ia/` | `compras/procesar-ia/` |
| `facturacion/compras/productos/...` | `compras/productos/...` |
| `facturacion/compras/item/...` | `compras/item/...` |
| `facturacion/compras/remito/...` | `compras/remito/...` |
| `facturacion/compras/comprobantes/...` | `compras/comprobantes/...` |
| `facturacion/compras/revisar-precios/` | `compras/revisar-precios/` |
| `facturacion/autorizaciones/` | `ventas/autorizaciones/` |
| `facturacion/preventas/...` | `ventas/preventas/...` |
| `facturacion/ventas/carga/` | `ventas/carga/` |
| `facturacion/ventas/productos/...` | `ventas/productos/...` |
| `facturacion/ventas/item/...` | `ventas/item/...` |
| `facturacion/ventas/autorizaciones/...` | `ventas/autorizaciones-venta/...` |
| `facturacion/ventas/clientes/...` | `ventas/clientes/...` |
| `facturacion/htmx/typeahead/...` | `htmx/typeahead/...` (sin prefijo módulo) |

---

### 3. Nuevas Vistas Index

#### [MODIFY] [views.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views.py)

- Reemplazar `FacturacionIndexView` por `ComprasIndexView` y `VentasIndexView` (ambos `TemplateView`).
- `ComprasIndexView` → template `facturacion/compras_index.html`
- `VentasIndexView` → template `facturacion/ventas_index.html`
- Cambiar el `redirect('facturacion_index')` en `AutorizacionesIndexView` a `redirect('ventas_index')`.

---

### 4. Nuevos Templates Index

#### [NEW] [compras_index.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/compras_index.html)
Cards: Carga de Compras, Listado de Compras, Compras Automática, Carga IA.

#### [NEW] [ventas_index.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/ventas_index.html)
Cards: Carga de Ventas, Carga de PreVentas, Bandeja de Autorizaciones.

#### [DELETE] [index.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/index.html)
Se elimina el index unificado (reemplazado por los dos nuevos).

---

### 5. Actualizar Botones "Volver" en Templates

| Template | Referencia actual | Nueva referencia |
|---|---|---|
| [compras_carga.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/compras_carga.html) | `facturacion_index` | `compras_index` |
| [compras_listado.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/compras_listado.html) | `facturacion_index` | `compras_index` |
| [ventas_carga.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/ventas_carga.html) | `facturacion_index` | `ventas_index` |
| [preventa_carga.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/preventa_carga.html) | `facturacion_index` | `ventas_index` |
| [autorizaciones_index.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/facturacion/autorizaciones_index.html) | `facturacion_index` | `ventas_index` |
| [caja_mostrador_abrir.html](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/templates/tesoreria/caja_mostrador_abrir.html) | `facturacion_index` | `ventas_index` |

---

## Verificación

### Manual
- Navegar a `/compras/` → carga correcta del index de Compras con sus 4 cards.
- Navegar a `/ventas/` → carga correcta del index de Ventas con sus 3 cards.
- Verificar que todos los sub-ítems del sidebar abren correctamente.
- Verificar que los botones "Volver" redirigen al index correcto.
- Verificar que la carga de compras, ventas y preventas siguen funcionando (guardar, redirect, etc.).
- Verificar que la bandeja de autorizaciones funciona desde `/ventas/autorizaciones/`.
- Verificar que el SVG de Contable se actualizó.
- Confirmar que `/facturacion/` ya no existe (404).

### Orden de Ejecución
1. Modificar `config/urls.py` (renombrar paths + agregar nuevos index).
2. Modificar `facturacion/views.py` (nuevas vistas index + redirect).
3. Crear templates `compras_index.html` y `ventas_index.html`.
4. Modificar `base.html` (sidebar).
5. Actualizar botones "Volver" en los 6 templates listados.
6. Eliminar `templates/facturacion/index.html`.
7. Actualizar `docs/walkthrough.txt`.
