# Plan de Implementación: Gestión de Caja Mostrador por Sucursal

Este plan detalla los pasos para implementar el diseño acordado, el cual establece que la sucursal operará como una dimensión analítica en los asientos contables y se controlará el flujo físico de efectivo, cheques y cupones de tarjeta a través de retiros y cierres de caja.

## Resoluciones de Diseño (Feedback del Usuario)

- **Migraciones:** Se avanzará con la creación de migraciones de esquema (`null=True`) sin script de backfill, ya que la base actual solo contiene registros de prueba.
- **Cuenta Puente:** La cuenta `Transferencias entre sucursales` se ubicará bajo el rubro ACTIVO -> ACTIVO CORRIENTE -> CAJA Y BANCOS, con la jerarquía `111009`.
- **Cierre de Caja:** El cajero ingresará únicamente el "importe total" declarado para el efectivo, sin detalle por denominaciones de billetes.
- **UI (Modales):** Se tomará como referencia conceptual el formulario legado (`cierre_caja_mostrador.scx`) para los datos a mostrar (Caja, Fecha, Cajero, Observaciones, Importes totales), pero implementado en Tailwind CSS para mantener la estética actual.

## Cambios Propuestos

### 1. Modelos `contable` (`contable/models.py`)
- **Asiento:** Añadir campo `sucursal = models.ForeignKey(Sucursal, null=True, blank=True, on_delete=models.PROTECT)`.
- **ParametrosContables:** Añadir las cuentas relacionadas a las cajas de mostrador y tesorería:
  - `cta_caja_mostrador`
  - `cta_caja_mostrador_dolares`
  - `cta_caja_central`
  - `cta_caja_central_dolares`
  - `cta_transferencias_sucursal`

### 2. Modelos `tesoreria` (`tesoreria/models.py`)
- **Valor:** Añadir `sucursal = models.ForeignKey(Sucursal, null=True, blank=True, on_delete=models.PROTECT)`.
- **CobroTarjeta:** Añadir `sucursal = models.ForeignKey(Sucursal, null=True, blank=True, on_delete=models.PROTECT)`.
- **Nuevos Modelos de Retiro y Cierre:**
  - `RetiroCaja(AuditModel)`: Cabecera del retiro/cierre.
  - `RetiroCajaValor(models.Model)`: Detalle de cheques.
  - `RetiroCajaTarjeta(models.Model)`: Detalle de cupones.
  - `RetiroCajaAsiento(models.Model)`: Relación N:M con los asientos contables generados.

### 3. Vistas `tesoreria` (`tesoreria/views_htmx.py`)
- Ajustar `caja_mostrador_procesar_cobro` para imputar a las nuevas cuentas de mostrador y propagar la `sucursal`.
- Crear vistas `caja_retiro_parcial`, `caja_cierre` y `caja_retiro_anular` con lógica de HTMX.

### 4. Templates `tesoreria`
- Crear `templates/tesoreria/modals/caja_retiro.html`
- Crear `templates/tesoreria/modals/caja_cierre.html`

## Plan de Pruebas
1. Migrar esquema.
2. Configurar parámetros contables en el sistema local.
3. Verificar el cobro de mostrador.
4. Validar que el retiro parcial asigne asientos simples o dobles (según la sucursal).
5. Verificar el cierre ciego de caja, los totales mostrados y la persistencia sin alterar el calculado.
