# Plan 102 — Integración de Padrón A4 / A5 (Constancia de Inscripción) para Validación Fiscal y Condición de IVA

**Responsable:** Gemini (Diseño de Plan) / Codex (Implementación)  
**Fecha:** 01 de Octubre de 2026  
**Módulo:** Facturación / Core (`facturacion/services/afip_padron.py`, `facturacion/views_htmx.py`, `templates/facturacion/modals/cliente_modal.html`)

---

## 1. Contexto y Objetivos

### Diagnóstico de la Situación Actual
Actualmente, el ERP dispone de `AFIPPadronService` (`facturacion/services/afip_padron.py`), el cual se conecta al servicio **Padrón A13** de AFIP (`ws_sr_padron_a13` con método `getPersonaV2`).
- **Limitación de A13:** Aunque A13 es excelente para obtener la identidad y el domicilio estandarizado (incluso de CUITs históricos), **AFIP no retorna en A13 los impuestos vigentes ni la condición frente al IVA** (fijando actualmente un valor por defecto `CONSUMIDOR FINAL`).
- **Requerimiento del Usuario:** Integrar el servicio **Padrón A4 / A5 (Constancia de Inscripción)** (`ws_sr_constancia_inscripcion` / `personaServiceA5` o `personaServiceA4`) para:
  1. Verificar si el CUIT está **válido y activo en AFIP** (o si registra baja/bloqueo fiscal).
  2. Determinar la **Condición de IVA real**: `RESPONSABLE INSCRIPTO`, `MONOTRIBUTO`, `EXENTO` o `CONSUMIDOR FINAL`.
  3. Potenciar y complementar el servicio A13 existente mediante una arquitectura híbrida tolerante a fallos.

---

## 2. Arquitectura de la Solución Técnica

### 2.1 Servicio `ws_sr_constancia_inscripcion` (A5) en `arca_arg`
AFIP expone el servicio de Constancia de Inscripción a través de WSAA:
- **Service Name (WSAA):** `ws_sr_constancia_inscripcion`
- **WSDL Homologación:** `https://awshomo.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl`
- **WSDL Producción:** `https://aws.afip.gov.ar/sr-padron/webservices/personaServiceA5?wsdl`
- **Método SOAP principal:** `getPersona(sign, token, cuitRepresentada, idPersona)` o `getPersona_v2`.

### 2.2 Motor de Detección Fiscal (`AFIPPadronService`)
Se actualizará `AFIPPadronService` para operar en **modo híbrido inteligente**:
1. **Paso 1: Consulta A5 / A4 (Validez y Condición Tributaria):**
   - Solicita Ticket de Acceso (TA) para `ws_sr_constancia_inscripcion`.
   - Consulta el CUIT.
   - Analiza `datosGenerales.estadoClave`:
     - `'ACTIVO'`: CUIT operativo y válido.
     - Otro estado (`'BAJA'`, `'INACTIVO'`, etc.): Extrae motivo de baja o bloqueo.
   - Analiza `datosRegimenGeneral` y `datosMonotributo`:
     - Si posee `datosMonotributo` activo o impuesto monotributo (código 20, 21, etc.) -> **`MONOTRIBUTO`**.
     - Si posee en `impuesto` el código 30 (IVA) -> **`RESPONSABLE INSCRIPTO`**.
     - Si posee en `impuesto` el código 32 (IVA Exento) -> **`EXENTO`**.
     - En ausencia de los anteriores -> **`CONSUMIDOR FINAL`**.
   - Extrae también actividades económicas registradas.

2. **Paso 2: Enriquecimiento Progresivo y Resiliencia Estricta (No-Bloqueo):**
   - **Tolerancia a falta de delegación:** Si la empresa tiene delegado A13 pero no A4/A5 en AFIP (o viceversa, o AFIP devuelve "Computador no autorizado"), el sistema **NO se rompe ni se frena**. Atrapa el error de forma controlada y continúa con el servicio que sí esté activo.
   - Si A4/A5 responde: se extraen validez, condición de IVA y actividades.
   - Si A13 responde: se extraen/enriquecen razón social y domicilio fiscal completo.
   - Si A4/A5 no está activo o falla pero A13 responde: se devuelve la ficha con los datos de A13 y un aviso informativo claro (`"aviso": "Servicio de Constancia/A4 no autorizado o inactivo en AFIP. Se cargaron datos base desde A13."`).
   - El frontend autocompleta todo lo obtenido y muestra el aviso en un toast o badge sin bloquear la carga.

3. **Estructura de Respuesta Uniforme:**
   ```json
   {
       "status": "success",
       "cuit": "20123456789",
       "razon_social": "PEREZ JUAN CARLOS",
       "tipo_persona": "F",
       "condicion_iva": "RESPONSABLE INSCRIPTO",
       "es_valido_afip": true,
       "estado_afip": "ACTIVO",
       "domicilio": "AV CORRIENTES 1234",
       "localidad": "SAN NICOLAS",
       "codigo_postal": "1043",
       "provincia": "CIUDAD AUTONOMA DE BUENOS AIRES",
       "actividades": ["SERVICIOS JURIDICOS"],
       "fuente": "A5+A13",
       "aviso": null
   }
   ```

---

## 3. Impacto en Archivos del Proyecto

| Archivo | Acción | Descripción del Cambio |
|---------|--------|------------------------|
| `Modelos/Facturacion AFIP/arca_arg/settings.py` | Modificar | Asegurar registro de WSDLs y nombres de servicio para `ws_sr_constancia_inscripcion` y `ws_sr_padron_a4`. |
| `facturacion/services/afip_padron.py` | Modificar | Incorporar cliente A5 (`ws_sr_constancia_inscripcion`), parser de impuestos/monotributo y estrategia híbrida de resolución con A13. |
| `facturacion/views_htmx.py` (`consultar_padron_afip`) | Modificar | Retornar los campos adicionales de validez (`es_valido_afip`, `estado_afip`) y condición de IVA real. |
| `templates/facturacion/modals/cliente_modal.html` | Modificar | Mapear la respuesta al selector de `condicion_iva`, notificar al usuario si el CUIT está inactivo/baja, y autocompletar la ficha. |

---

## 4. Plan de Pruebas

1. **Pruebas Unitarias Automatizadas:**
   - Test de parsing de respuesta A5 con CUIT Responsable Inscripto.
   - Test de parsing de respuesta A5 con CUIT Monotributista.
   - Test de detección de CUIT dado de baja / inactivo.
   - Test de fallback resiliente ante fallas de conexión.
2. **Pruebas de Integración en Django Shell:**
   - Consulta con credenciales reales de empresa activa sobre CUITs de prueba conocidos.
3. **Pruebas de Interfaz (Modal de Clientes):**
   - Ingreso de CUIT en el modal, clic en 🔍 -> verificación de autoselección de Condición de IVA y advertencia visual si está inactivo.
