# Plan 044: Trazabilidad Multi-Ciclo (Recompras de Subproductos)

## Descripción y Arquitectura del Negocio
La lógica de trazabilidad de armas u objetos seriados exige un circuito transaccional auditable. En lugar de sobrescribir el estado de una misma arma en la base de datos (lo que corrompe el historial de quién fue el propietario anterior y las fechas), cada vez que el negocio ingresa un arma a su depósito (ya sea nueva, o recomprada a un tercero) se genera **un nuevo registro en la tabla `Subproducto`**, asociado al `compra_id` correspondiente. Cuando el arma sale, se graba en ese mismo registro el `id_vta`.
De este modo, una búsqueda de la historia de un arma devolverá N registros ordenados en el tiempo con todas las transacciones de ingreso/egreso.

Para habilitar este circuito sin corromper el stock actual, se requiere un trabajo coordinado en 3 capas.

## 1. Capa de Base de Datos (Modelos)
El modelo `Subproducto` (en `productos/models.py`) actualmente tiene la restricción `unique=True` en el campo `serie`. Esta restricción de PostgreSQL lanza un `IntegrityError` al intentar registrar el mismo número de serie por segunda vez. 
- **Cambio:** Remover `unique=True` de la declaración del campo `serie`.

## 2. Capa de Seguridad (Protección contra Duplicados Activos)
Si bien la base de datos ahora permite series repetidas, el sistema debe impedir por software que un operario ingrese una serie que **ya se encuentra activa bajo nuestro techo** (en depósito, taller, consignación, etc). 
- **Validación Principal:** Al intentar cargar una serie por Compras Comunes o Trazabilidad, el sistema verificará:
  `Subproducto.objects.filter(serie__iexact=serie, empresa_id=...).exclude(situacion='VENDIDA').exists()`
- Si da positivo, se rechaza. Si da falso, se permite el ingreso (porque la serie no existía, o todas las veces que ingresó ya se encuentra VENDIDA/despachada).
- **Implementación (Vistas):** 
  1. En `facturacion/views_trazabilidad.py` (`compras_trazabilidad_item_add`): Actualizar el filtro `.exists()` al cargar al carrito.
  2. En `facturacion/views_htmx.py` (`guardar_series_item`): Agregar esta misma lógica al agregar el carrito de compras comunes.
  3. En `facturacion/views.py` (`ComprasCargaView.post`): Validar esto en el backend rígido, deteniendo la transacción si alguna serie falla la verificación.

## 3. Capa de Egreso (Ventas Trazabilidad)
Para vender un arma de trazabilidad, el usuario pistolea el código. Como puede haber 3 o 4 registros con el mismo código en la base de datos, el sistema debe traer el registro actual (el activo).
- **Implementación (Vistas):**
  En `facturacion/views_trazabilidad.py` (`agregar_item_venta_trazabilidad`): 
  Cambiar la búsqueda que actualmente está en `get(situacion='DEPOSITO')` por:
  `filter(serie__iexact=serie, empresa_id=empresa_id).exclude(situacion='VENDIDA').first()`. 
  Esto garantiza que el sistema encontrará el arma independientemente de su situación. Al estar blindado el punto 2, matemáticamente siempre habrá como máximo un (1) registro activo.
