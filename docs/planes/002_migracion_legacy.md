# Plan de Migración de Base de Datos Legacy a PostgreSQL

## Objetivo
El objetivo de este plan es definir la estrategia, los requerimientos, y los pasos metodológicos para realizar la migración completa y segura de los datos desde la base de datos antigua (Legacy) hacia el nuevo esquema estructurado en PostgreSQL del ERP Ikigai 2.

## 1. Cosas a tener en cuenta (Checklist Técnico)

Para lograr una migración exitosa, se deben evaluar los siguientes puntos de fricción comunes:

### A. Mapeo de Tipos de Datos y Longitudes
- **Cadenas de texto**: Asegurar que los VARCHAR del legacy no excedan los límites definidos en los `CharField` de Django (ej. si un RUT/CUIT tiene 20 caracteres en legacy, en Django debe soportarlo).
- **Numéricos y Moneda**: En el legacy pueden ser Flotantes (`float`), pero en el nuevo ERP deben ser obligatoriamente insertados en `DecimalField` (contable, facturación, tesorería) para no perder precisión.
- **Fechas**: Conversión de formatos de fecha `YYYY-MM-DD` y manejo de zonas horarias (`timezone-aware` datetime).

### B. Mantenimiento de Referencias (Claves Foráneas)
- Es imperativo agregar un campo `codigo_anterior` (o `legacy_id`) en las tablas maestras de Django (clientes, productos, cuentas contables). Esto ya se ha empezado a hacer en algunos modelos. Este campo permite:
  1. Que los scripts de migración sean **idempotentes** (si el script se corta por la mitad, al reiniciar busque por `codigo_anterior` y use `update_or_create`).
  2. Poder auditar si un registro migró cruzándolo con el Excel/CSV original.

### C. Orden de Inserción (Dependencias Topológicas)
Para no violar las restricciones de claves foráneas (`IntegrityError`), el orden de ejecución debe ser:
1. **Nivel 1 (Sin dependencias)**: Usuarios, Categorías, Unidades de Medida, Marcas, Rubros, Tipos de Impuestos, Cuentas Contables base.
2. **Nivel 2 (Dependen de Nivel 1)**: Productos, Clientes, Proveedores, Almacenes, Listas de Precios (Tarifas).
3. **Nivel 3 (Transaccional, dependen de Nivel 2)**: Facturas, Ventas, Movimientos de Stock, Asientos Contables, Transacciones de Caja/Bancos.

### D. Limpieza y Sanitización (Data Cleansing)
- **Nulos y Vacíos**: Django es estricto. Si un campo en Django tiene `null=False`, los scripts deben reemplazar nulos legacy por valores por defecto (ej. string vacío `""` o un ID por defecto).
- **Duplicados**: Detectar si en el legacy hay 2 clientes con el mismo CUIT/RUT pero en Django es único, y decidir cuál se fusiona o cómo se soluciona.

### E. Integridad Transaccional y Performance
- **Atomicidad**: Usar `transaction.atomic()` en los comandos de migración. Si un bloque de 1000 registros falla, se hace rollback y la DB no queda sucia.
- **Manejo de Signals**: En Django, al crear una Venta, puede que salte un *Signal* o un método `save()` que afecte stock. Durante la migración **del histórico**, se deben desactivar estos automatismos (porque el histórico de stock ya vendrá explícito) o procesarlos secuencialmente a sabiendas de que tomará más tiempo.

## 2. Acciones del lado del ERP Nuevo (Este lado)

Se ha creado un script base automatizado (`exportar_diccionario.py`) para extraer en un formato amigable (.csv o excel) la estructura actual y real de la base de datos PostgreSQL de las aplicaciones:
- `empresas`, `usuarios`, `productos`, `facturacion`, `tesoreria`, `contable`

Esto permitirá entregar un diccionario de datos del destino para que se pueda hacer el cruce manual o en Excel con las columnas del Legacy.

## 3. Siguientes Pasos
1. **Evaluar el diccionario generado**: Se encuentra en `scratch/diccionario_postgres.csv` (una vez generado).
2. **Construir el mapa de conversión**: Un archivo de mapeo (ej. Tabla `CLIENTES` legacy -> Tabla `facturacion_clienteproveedor` en Django, Campo `Nombre` -> `razon_social`).
3. **Adaptar scripts en `migracion/management/commands`**: Completar los scripts usando lógica `update_or_create` basada en el código anterior.

## Archivos Impactados:
- `docs/planes/002_migracion_legacy.md` (Este archivo).
- `migracion/management/commands/exportar_diccionario.py` (Script creado para asistir en la extracción del diccionario de datos de los modelos).
- `scratch/diccionario_postgres.csv` (Archivo resultante a compartir).
