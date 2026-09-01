# Plan de Implementación: Carga Inicial de Tipos de Comprobantes (Aprobado)

El objetivo de este plan es poblar la tabla `TipoComprobante` de la aplicación `facturacion` utilizando los datos proporcionados en el archivo `c:\borrador\comprobantes.csv`. 

## Decisiones y Criterios Aprobados

1. **Formato del Código:** El modelo tiene `codigo` como `CharField(max_length=3)`. Se respeta el formato numérico de ARCA, por lo que los códigos se guardarán con 3 dígitos (ej: `1` se guardará como `001`, `110` como `110`).
2. **Campo Estado:** Solo los comprobantes del `001` al `008` (usados inicialmente por la empresa de prueba) se configurarán con `estado = True`. El resto se importará con `estado = False` para no ensuciar la interfaz de **Ventas**.
  * **Nota sobre Compras:** En el módulo de Compras no se respetará este filtro de `estado`. Todos los comprobantes serán susceptibles de ser seleccionados, contando con un buscador integrado que opere indistintamente por código o descripción.
3. **Mecanismo:** Se creará un "Management Command" de Django para permitir futuras actualizaciones si ARCA determina nuevos códigos.

## Cambios a Realizar

### Módulo `facturacion`

Creación de un comando de administración (Management Command).

#### [NEW] facturacion/management/commands/importar_comprobantes.py
Se creará este archivo (junto con las carpetas `management/commands`).
El comando leerá el archivo CSV y utilizará `update_or_create` de Django para evitar duplicados y actualizar descripciones si cambian en el futuro.

- Mapeo de columnas:
  - `codigo` (CSV) -> `codigo` (zfill 3 dígitos).
  - `descripcion` (CSV) -> `detalle` (truncado a 100 caracteres).
  - `signo` (CSV) -> `signo` (entero).
  - `estado` -> `True` si código está entre "001" y "008", caso contrario `False`.

## Plan de Pruebas

### Manual Verification
- Ejecutar el comando: `python manage.py importar_comprobantes "c:\borrador\comprobantes.csv"`
- Verificar la correcta carga consultando `TipoComprobante.objects.count()`.
