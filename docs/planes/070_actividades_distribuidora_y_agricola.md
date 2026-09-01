# Plan 070: Opciones de Actividades Distribuidora y Empresa Agrícola

**Fecha**: 2026-08-24  
**Objetivo**: Incorporación de dos nuevos tipos de actividad a nivel de `Empresa`: **Distribuidora** y **Empresa Agrícola**, en el selector / combobox de alta y edición de empresas.

---

## 1. Cambios Realizados

### A. Módulo `empresas` (`Empresa`)
* Incorporación de la tupla `TIPO_ACTIVIDAD_CHOICES` en `Empresa` (`empresas/models.py`):
  * `('DISTRIBUIDORA', 'Distribuidora')`
  * `('AGRICOLA', 'Empresa Agrícola')`
* Asignación de `choices=TIPO_ACTIVIDAD_CHOICES` en `Empresa.tipo_actividad`.
* Actualización de `EmpresaForm` (`empresas/forms.py`) para utilizar las nuevas opciones en la interfaz visual de alta y edición de empresas.

### B. Migración de Base de Datos
* Migración generada y aplicada: `empresas/migrations/0016_alter_empresa_tipo_actividad.py`.
