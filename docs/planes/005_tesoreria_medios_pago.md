# Plan 005 — Tesorería y Medios de Pago

## Estado: 🔶 En Progreso (Fase 6 del walkthrough — falta: vistas de emisión de Recibos/OP)

## Objetivo
Mover la entidad lógica de Cuenta Bancaria hacia el módulo correcto (Tesorería), reemplazar los "tipos" de valores hardcodeados por un modelo maestro configurable de `MedioPago` vinculable a la contabilidad, y agregar el ABM correspondiente al Panel de Configuración general.

## Cambios Realizados

1. **Modelos de Tesorería (`tesoreria/models.py`)**:
   - Creación del modelo maestro `MedioPago` para configurar métodos de cobro/pago vinculados a cuentas contables (Efectivo, Mercado Pago, etc.).
   - Criterio funcional: Mercado Pago se parametriza como `Billetera Digital` (`DIG`) y no como banco. Aunque funcionalmente sea la billetera más cercana a un banco, en el sistema debe quedar como medio de pago digital/PSP.
   - Migración del modelo `CuentaBancaria` (física) desde el módulo `contable` hacia `tesoreria`. 
   - Refactorización del modelo `Valor` para usar `MedioPago` a través de Foreign Key y la adición opcional de Foreign Key a `CuentaBancaria`.

2. **Modelos Contables (`contable/models.py`)**:
   - Eliminación de la clase `CuentaBancaria` y ajuste de las referencias en formularios y vistas de este módulo a `tesoreria.models.CuentaBancaria`.

3. **Centralización de Parametrizaciones en Configuración**:
   - Se añadió una sección de **Tesorería** al Hub de configuración (`hub.html`) con los ABMs de `Medios de Pago` y `Cuentas Bancarias`.
   - Se añadió una sección de **Contabilidad** al Hub de configuración con el ABM de `Plan de Cuentas`.
   - Se movieron los templates y vistas HTMX de cuentas contables y bancarias de `contable/` a `configuracion/`.
   - El módulo contable ahora solo contiene vistas operativas: Libro Diario, Mayor y Balance.
   - Se corrigió bug de `request` vs `self.request` en `views_config.py` (CBV).

4. **Migraciones**:
   - Se ejecutaron los comandos `makemigrations` y `migrate` impactando las tablas en la Base de Datos PostgreSQL.
   - Se normalizó la tabla física del maestro `MedioPago` a `tesoreria_medio_pago`.
   - Se agregó la migración `tesoreria.0004_rename_mediopago_table_if_needed` para renombrar condicionalmente `teso_medio_pago` a `tesoreria_medio_pago` en bases donde la tabla vieja ya existía.

## Próximos Pasos
- Diseño de las pantallas operativas (Vistas) para "Emitir Recibo" o "Emitir Orden de Pago".
- Integración de los `MediosPago` en el frontend operativo de cobros y pagos para generación automática de la cartera de valores (Caja/Bancos).
