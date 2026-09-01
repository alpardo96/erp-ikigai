# Plan 016 — Módulo de Cierre de Ejercicio (Futuro)

## Estado: ❌ Pendiente

## Objetivo
Desarrollar un módulo robusto para gestionar el Cierre de Ejercicio Contable. Se debe evitar cierres accidentales, controlar las fechas valor de los asientos posteriores al cierre, y permitir ajustes de auditoría.

## Requerimientos y Lógica a Implementar
1. **Ubicación de la Acción:** Mover el botón o la acción de "Cierre de Ejercicio" a la pantalla de configuración de `ParametrosContables` o dentro de la gestión de `Ejercicios` en el módulo de Empresas.
2. **Control de Fechas:** 
   - Un ejercicio cerrado debe quedar bloqueado.
   - Cualquier intento de registrar un movimiento (compra, venta, asiento, recibo) con fecha correspondiente a un ejercicio ya cerrado debe ser rechazado por el sistema.
   - Manejo de "fecha valor": Si se carga un comprobante viejo de un ejercicio cerrado, debe contabilizarse en el primer día hábil del ejercicio abierto actual, dejando constancia de la fecha original del comprobante.
3. **Ajustes de Auditoría:**
   - Permitir a usuarios con permisos especiales (ej. Contador/Auditor) "reabrir" un ejercicio temporalmente o ingresar asientos de ajuste al cierre (Asientos de periodo 13).
4. **Anulación Segura:**
   - Si se anula el asiento de cierre, el ejercicio vuelve a estado "Abierto".

## Modelos Implicados
- `empresas.Ejercicio`: Agregar campo `estado` (Abierto, Cerrado, En Auditoría).
- `contable.Asiento`: Validar en el `save()` o en el servicio de contabilización que la fecha del asiento pertenezca a un ejercicio abierto.

## Servicios a Modificar
- `contable.services.cierre`: Refactorizar para incluir el cambio de estado del `Ejercicio`.
- `facturacion.services.*` y `tesoreria.services.*`: Modificar la obtención del ejercicio para que verifique que esté abierto.

## Tareas Previas Requeridas
- Módulo de Permisos Modulares (para validar quién puede reabrir o cerrar).
