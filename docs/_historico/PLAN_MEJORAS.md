# Plan de Mejoras Priorizado — ERP Ikigai

> Documento de trabajo. Cada ítem incluye **por qué importa**, **criterio de "hecho"** y, en los puntos críticos, un **ejemplo de implementación**.
> Orden = prioridad descendente. Los primeros bloques son los que sostienen la integridad contable; los últimos son higiene y mantenimiento.

---

## Prioridad 1 — Integridad transaccional (saldos, stock, movimientos)

### 1.1. Centralizar el cálculo de saldos en un único punto atómico

**Problema actual.** `ClienteProveedor.saldo`, `Compra.saldo/pagado`, `Venta.saldo/cobrado` y `Movimiento.saldo` viven cada uno por su cuenta. Si una de las cuatro fuentes se actualiza sin las demás, el saldo del cliente miente. Para un ERP contable, esto es el riesgo más serio del sistema hoy. (dejamos solamente saldo y tendra un tratamiento similiar al stock de productos sin olvidar que la tabla incluye tanto clientes como proveedores).

**Estrategia recomendada.** Reemplazar la actualización dispersa por un **servicio único** (`contable/services/saldos.py`) que se invoque dentro de `transaction.atomic()` cada vez que se crea, modifica o anula una compra/venta/cobro/pago. El servicio recalcula desde cero a partir de los comprobantes y deja el saldo en `ClienteProveedor`. Nada fuera del servicio puede tocar `saldo`.

**Ejemplo:**

```python
# contable/services/saldos.py
from django.db import transaction
from django.db.models import Sum, F
from facturacion.models import ClienteProveedor, Venta, Compra

@transaction.atomic
def recalcular_saldo_cliente(cliente_id: int) -> None:
    cliente = ClienteProveedor.objects.select_for_update().get(pk=cliente_id)
    ventas_pendientes = Venta.objects.filter(
        cliente=cliente, estado=0
    ).aggregate(s=Sum(F('total') - F('cobrado')))['s'] or 0
    cliente.saldo = cliente.saldo_inicial + ventas_pendientes
    cliente.save(update_fields=['saldo'])
```

Después se invoca desde signals o desde las views de carga, siempre con `transaction.atomic` envolviendo la operación completa.

**Criterio de hecho.** Existe `contable/services/saldos.py`; las views y signals lo usan; no hay asignación directa a `cliente.saldo` fuera del servicio (verificable con `grep "\.saldo\s*=" --include="*.py"`).

---

### 1.2. Decidir el rol del modelo `Movimiento`: fuente única o vista materializada

**Problema actual.** `Movimiento` duplica `fecha`, `tipo`, `punto`, `numero`, `cli_pro` que ya viven en `Compra` y `Venta`. Si una venta se edita, el movimiento asociado queda con datos viejos.

**Dos caminos válidos (elegir uno, no ambos):**

- **(A) Vista materializada / read-only.** El movimiento se regenera con un management command o signal `post_save`. Nadie lo edita a mano. Sirve para informes rápidos (kardex, ranking, etc.) sin pegarle a las tablas operativas.
- **(B) Fuente única.** Compras/ventas dejan de tener campos redundantes y todo se lee desde `Movimiento`. Más limpio conceptualmente, pero implica una refactorización grande.

**Recomendación.** Camino (A): más barato, te da los informes sin tocar lo que ya funciona. Eliminá los campos redundantes que se puedan derivar (`tipo`, `punto`, `numero` quedan en el comprobante; `Movimiento` referencia con FK y listo). Aceptamos la recomendacion

**Criterio de hecho.** `Movimiento` se genera automáticamente desde signals de `Compra` y `Venta`. No hay views que lo creen manualmente. Editar una venta regenera su movimiento.

---

### 1.3. Encapsular actualización de stock en signals

**Problema actual.** No se ve lógica en `CompraItem` / `VentaItem` que actualice `Producto.stock` o `StockSucursal.cantidad`. Si vive en las views, hay riesgo de que un flujo alternativo (admin, import, shell) salte la actualización.

**Solución.** Signals `post_save` y `post_delete` sobre los modelos `Item`, llamando a un servicio `stock_service.aplicar_movimiento(item, signo)` envuelto en `transaction.atomic`. Para evitar el clásico problema de doble suma en updates, guardar la cantidad anterior en `__init__` o usar `pre_save` para calcular el delta.

**Criterio de hecho.** Crear, editar o eliminar un `CompraItem`/`VentaItem` desde cualquier punto (view, admin, shell) actualiza `StockSucursal` correctamente. Test unitario que lo verifique.

---

### 1.4. Mover el cálculo de totales de la cabecera al modelo

**Problema actual.** No queda claro dónde se calcula `Compra.neto + iva + ... = total`. Si es en el form, otros flujos pueden romperlo.

**Solución.** Método `recalcular_totales()` en `Compra` y `Venta`, invocado desde signals de `Item.post_save/post_delete`. La cabecera nunca se guarda con totales calculados a mano.

**Criterio de hecho.** Cargar 3 items con IVA distinto y validar que `compra.total` coincide con la suma esperada, sin que la view haya intervenido.

---

## Prioridad 2 — Tests de las reglas críticas

No se necesita cobertura del 100%, pero sí cubrir lo que, si se rompe, te genera un problema con un cliente. Mínimo viable:

| Test | App | Qué verifica |
|------|-----|--------------|
| `test_ejercicio_no_solapa` | `empresas` | Que `clean()` rechace ejercicios con fechas que se pisan |
| `test_ejercicio_orden_fechas` | `empresas` | Que `inicio > cierre` falle |
| `test_saldo_cliente_recalculo` | `contable` | Crear venta, cobro parcial, verificar saldo |
| `test_stock_post_compra` | `productos` | Compra → stock sube; eliminar item → stock vuelve |
| `test_stock_post_venta` | `productos` | Venta → stock baja, no permite negativo (o sí, según política) |
| `test_tipo_doc_99` | `facturacion` | Forzar tipo 99 → cuit='0', tipo_entidad=1, MINORISTA |
| `test_uppercase_save` | `facturacion` | razón social en minúsculas → se guarda mayúscula |
| `test_total_iva_alicuotas_mixtas` | `facturacion` | Cabecera coincide con suma de items con 21% y 10.5% |

**Estrategia.** Usar `pytest-django` o el runner nativo. Fixtures con `factory_boy` para no pelearse con FK obligatorias.

**Criterio de hecho.** `python manage.py test` corre en menos de 30 segundos y pasa. Se ejecuta antes de cada commit importante.

---

## Prioridad 3 — Consistencia y normalización de modelos

### 3.1. Unificar el tipo de comprobante

`Compra.tipo` y `Venta.tipo` son FK a `TipoComprobante`, pero `Movimiento.tipo` es `IntegerField` libre. Cambiar a FK también en `Movimiento` para garantizar referencias válidas.

### 3.2. Validar `clasificacion` de `ClienteProveedor` a nivel modelo

Hoy depende del form. Mover la validación a `clean()`:

```python
def clean(self):
    if self.tipo_entidad == 1 and self.clasificacion not in dict(self.CLASIFICACION_CLI):
        raise ValidationError({'clasificacion': 'Clasificación inválida para cliente'})
    if self.tipo_entidad == 2 and self.clasificacion not in dict(self.CLASIFICACION_PRO):
        raise ValidationError({'clasificacion': 'Clasificación inválida para proveedor'})
```

Y llamar `full_clean()` antes del `save()` (o usar un `ModelForm` que ya lo hace).

### 3.3. Choices de moneda inconsistentes

En `Compra`/`Venta` el euro es `'60'`, en `CuentaBancaria` es `'060'`, en `Subproducto` es `'EUR'`. Definir un único `MONEDA_CHOICES` en `core/constants.py` e importarlo desde todos lados. Si hay datos cargados con códigos distintos, agregar una migración de datos.

### 3.4. Permisos modulares más flexibles

`Perfil.permiso_armeria_*` y `permiso_josen_*` están hardcoded. Si sumás un rubro nuevo, migración obligatoria. Migrar a:

```python
class ModuloNegocio(models.Model):
    codigo = models.CharField(max_length=20, unique=True)  # 'armeria', 'josen', ...
    nombre = models.CharField(max_length=100)

class PermisoUsuarioModulo(models.Model):
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE)
    modulo = models.ForeignKey(ModuloNegocio, on_delete=models.CASCADE)
    puede_ver = models.BooleanField(default=False)
    puede_editar = models.BooleanField(default=False)
    class Meta:
        unique_together = ('perfil', 'modulo')
```

Sumar módulos nuevos pasa a ser un insert, no una migración.

**Criterio de hecho.** Crear un módulo "Inmobiliaria" y asignarle permisos a un usuario sin tocar código.

---

## Prioridad 4 — Higiene de proyecto

### 4.1. Sacar respaldos del repo

`Respaldo_20260513/` y `respaldo_diario.bat` dentro del proyecto mezclan código y datos. Mover los respaldos a `D:\JM_Soft\Respaldos\erp-ikigai\` y agregar `Respaldo_*/` al `.gitignore`. El `.bat` puede quedar en el repo si solo contiene comandos, pero el output va afuera.

### 4.2. Squash de migraciones antes de producción

15 migraciones en `facturacion`, 13 en `productos`. Funciona, pero antes del primer deploy "real" conviene `python manage.py squashmigrations facturacion 0001 0015` para dejar el historial limpio. Hacerlo una sola vez y nunca con datos en producción.

### 4.3. Pre-commit hooks

`pre-commit` con `black`, `ruff`, y `django-upgrade`. Evita reformateos manuales y deja un código uniforme. Configuración mínima en `.pre-commit-config.yaml`.

### 4.4. Logging estructurado

Hoy el `settings.py` no define `LOGGING`. Para un ERP, conviene un logger por app que vaya a archivo rotativo (`logs/erp-ikigai.log`). Cuando algo falla en producción, sin logs es a ciegas.

---

## Prioridad 5 — Documentación interna

### 5.1. `README.md` con setup local

Cómo levantar el proyecto: crear venv, instalar requirements, restaurar dump de Postgres, correr migraciones, crear superuser, `npm run build`, `python manage.py runserver`. Te ahorra explicar lo mismo dos veces si sumás a alguien.

### 5.2. `CHANGELOG.md`

Para registrar cambios funcionales (no técnicos) por fecha. Útil cuando un cliente pregunta "¿desde cuándo cambió esto?".

### 5.3. Diagrama de entidades

Un diagrama (puede ser Mermaid en el README) mostrando relaciones entre `Empresa → Sucursal → Ejercicio → Venta/Compra → Items → Producto`. Es la "foto" del dominio para vos del futuro y para cualquier consultor que mires el código.

---

## Prioridad 6 — Seguridad (último, según lo acordado)

Para activar **antes del primer uso real con datos productivos**:

1. **Variables de entorno.** `django-environ` con archivo `.env` no versionado. Mover `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, credenciales de DB.
2. **Rotar password de Postgres.** El actual está en el repo: cambiarlo en la base y en `.env`.
3. **`DEBUG = False`** en producción + `ALLOWED_HOSTS` explícito.
4. **CSRF y sesiones seguras.** `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True` cuando haya HTTPS.
5. **Backup automático cifrado.** `pg_dump` + `gpg` + destino fuera del servidor.
6. **Permisos a nivel de DB.** Usuario aplicación distinto del superuser de Postgres, con solo SELECT/INSERT/UPDATE/DELETE en las tablas del schema.
7. **Auditoría de accesos.** Loguear logins (éxito y falla) y operaciones sensibles (anulación de comprobantes, baja de cliente).

**Criterio de hecho.** Clonar el repo en una máquina limpia no expone ninguna credencial. `python manage.py check --deploy` pasa sin warnings críticos.

---

## Orden de ataque sugerido (próximas 4–6 semanas)

| Semana | Foco |
|--------|------|
| 1 | 1.1 (servicio de saldos) + 2 (primeros 3 tests) |
| 2 | 1.3 (stock en signals) + 1.4 (totales en cabecera) + tests asociados |
| 3 | 1.2 (decisión y refactor de `Movimiento`) |
| 4 | 3.1 + 3.2 + 3.3 (normalizaciones de modelos) + tests |
| 5 | 3.4 (permisos modulares) + 4.1, 4.3, 4.4 (higiene) |
| 6 | 5 (documentación) y preparación para 6 (seguridad) |

Cada bloque es chico, se puede frenar y retomar sin perder hilo, y al final de cada semana queda algo verificable con tests.
