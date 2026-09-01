# Plan de Implementación: Replicación de Plan de Cuentas, Parámetros, Medios de Pago y Cuentas Bancarias (Empresa ID=1 -> Empresa ID=3)

Este plan amplía la estrategia técnica para duplicar/replicar el catálogo completo de cuentas contables (`contable.models.Cuenta`), los parámetros contables (`contable.models.ParametrosContables`), las cuentas bancarias (`tesoreria.models.CuentaBancaria`) y sembrar los Medios de Pago (`tesoreria.models.MedioPago`) desde la Empresa origen (`empresa_id = 1`) hacia la Empresa destino (`empresa_id = 3`).

## User Review Required

> [!IMPORTANT]
> - **Empresa Origen (ID=1)**: Lopez Rios y Asoc SA.
> - **Empresa Destino (ID=3)**: EMPRESA TEST.
> - Se actualizará el comando de Django `python manage.py replicar_plan_cuentas --origen 1 --destino 3` para ejecutar las 4 fases en forma atómica y segura con `transaction.atomic()`.

## Open Questions

- Ninguna. La estructuración de Medios de Pago se enlazará automáticamente con las cuentas contables de `ParametrosContables` de la Empresa 3.

## Proposed Changes

### Módulo Contable y Tesorería

#### [MODIFY] [replicar_plan_cuentas.py](file:///d:/JM_Soft/erp-ikigai-2/contable/management/commands/replicar_plan_cuentas.py)
- **Extensión de la Lógica de replicación**:
  1. **Pasada 1 - Creación/Sincronización de Cuentas**: Duplicado atómico de las 247 cuentas contables.
  2. **Pasada 2 - Asignación Jerárquica (`sumariza`)**: Reasignación de padres/hijas.
  3. **Pasada 3 - Parámetros Contables (`ParametrosContables`)**: Clonado de parámetros con sus 23 claves foráneas mapeadas a las cuentas de Empresa 3.
  4. **Pasada 4 - Replicación de Cuentas Bancarias (`CuentaBancaria`)**:
     - Clonado de las cuentas bancarias registradas en la Empresa 1 hacia la Empresa 3 (ej. Banco Patagonia, Banco Credicoop, Banco Galicia).
     - Mapeo de sus Foreign Keys `cuenta_contable` y `cuenta_contable_cheques` a sus equivalentes clonadas en la Empresa 3.
  5. **Pasada 5 - Migración / Sembrado de Medios de Pago (`MedioPago`)**:
     - Creación y vinculación de los Medios de Pago estándar (`EFE-ARS`, `EFE-USD`, `CHQ-TER`, `TRA-BCO`, `TAR-CRE`, `RET-GAN`, `RET-IVA`, `RET-IIBB`, `RET-SUSS`, `RET-PR-GAN`, `RET-PR-IVA`, `RET-PR-IIBB`) para la Empresa 3 (y Empresa 1 si faltasen), enlazados a las cuentas contables de su correspondiente `ParametrosContables`.

---

### Documentación e Histórico

#### [MODIFY] [065_replicar_plan_cuentas.md](file:///d:/JM_Soft/erp-ikigai-2/docs/planes/065_replicar_plan_cuentas.md)
- Actualización de la documentación histórica en `docs/planes/`.

---

## Verification Plan

### Automated Tests / Commands
- Ejecución del comando extendido:
  ```powershell
  .\venv\Scripts\python.exe manage.py replicar_plan_cuentas --origen 1 --destino 3
  ```
- Verificación por consola de Python:
  ```powershell
  .\venv\Scripts\python.exe -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from tesoreria.models import MedioPago, CuentaBancaria; print('MediosPago E3:', list(MedioPago.objects.filter(empresa_id=3).values('codigo', 'nombre', 'cuenta_contable__cuenta'))); print('CuentasBancarias E3:', list(CuentaBancaria.objects.filter(empresa_id=3).values('banco', 'cuenta_contable__cuenta')))"
  ```

### Manual Verification
- Comprobación de que la carga de Recibos, Órdenes de Pago y Caja Mostrador en la Empresa 3 reconozca los medios de pago configurados sin arrojar errores de medios faltantes.
