# Plan 062: Incorporación de Costo de Reposición (cto_rep) en VentaItem

**Fecha:** 21 de Agosto de 2026  
**Módulo:** Facturación / Productos  

## Descripción
Se agregará el campo `cto_rep` (Costo de Reposición) al modelo `VentaItem` (`facturacion_ventaitem`) en la app de `facturacion`. Este campo registrará de forma inmutable el costo de reposición vigente del producto (`productos_producto.cto_rep`) en el instante exacto en que se realiza la venta.

Con esta incorporación, el ERP Ikigai 2 podrá determinar el **Margen Bruto**, la **Contribución Marginal** y el **Punto de Equilibrio** por ítem y por comprobante de venta, de manera independiente a futuras fluctuaciones en los costos de reposición de la tabla de productos.

---

## Cambios Propuestos

### 1. Modelo de Facturación (`facturacion/models.py`)
- **Agregar campo en `VentaItem`**:
  ```python
  cto_rep = models.DecimalField(
      max_digits=15,
      decimal_places=2,
      default=0,
      verbose_name="Costo de Reposición",
      help_text="Costo de reposición vigente del producto al momento de realizar la venta"
  )
  ```
- **Lógica de Autocompletado en `VentaItem.save()`**:
  ```python
  def save(self, *args, **kwargs):
      if (self.cto_rep is None or self.cto_rep == 0) and self.producto_id:
          self.cto_rep = self.producto.cto_rep
      super().save(*args, **kwargs)
  ```
- **Propiedades calculadas en `VentaItem`**:
  - `@property subtotal_costo_reposicion`: `self.cantidad * self.cto_rep`
  - `@property contribucion_marginal_unitaria`: `(self.precio_unitario * (1 - self.porcentaje_descuento / 100)) - self.cto_rep`
  - `@property contribucion_marginal_total`: `self.contribucion_marginal_unitaria * self.cantidad`
- **Propiedades calculadas en `Venta`**:
  - `@property total_costo_reposicion`: `sum(item.subtotal_costo_reposicion for item in self.items.all())`
  - `@property contribucion_marginal_total`: `sum(item.contribucion_marginal_total for item in self.items.all())`
  - `@property margen_bruto_porcentaje`: porcentaje global de margen de la venta.

---

### 2. Servicios de Facturación y Notas de Crédito
- En `facturacion/services/notas_credito.py`:
  - Al crear el `VentaItem` de la Nota de Crédito a partir de un `original_item`, asignar explícitamente `cto_rep=original_item.cto_rep` para conservar el costo original de reposición del ítem que fue vendido.

---

### 3. Pruebas Automatizadas
- Nuevo test `facturacion/tests/test_costo_reposicion.py` que verifica:
  1. Guardado automático de `cto_rep` desde el producto.
  2. Inmutabilidad del `cto_rep` grabado en la venta tras cambios en el costo del producto.
  3. Cálculo correcto de la contribución marginal y total de costo de reposición.

---

## Plan de Verificación
- Ejecución de `python manage.py test facturacion.tests.test_costo_reposicion`
- Ejecución de `python manage.py test facturacion`
