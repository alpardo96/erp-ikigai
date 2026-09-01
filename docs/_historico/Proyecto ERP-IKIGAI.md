**Proyecto: erp-ikigai**  
   
***Descripcion breve:***  
 ERP de gestión administrativa y contable, centrado fundamentalmente en las 4 operaciones básicas de gestión comercial: ventas, compras, cobranzas y pagos en sus distintas facetas conforme el tipo de empresa usuaria.

Módulos principales:  
1\. Ventas  
1.1. Facturación de Productos  
1.2. Facturación Genérica: no identificamos productos  
1.3. Facturación por Lotes  
1.4. Facturas manuales   
1.5. Listado de Saldos de Clientes  
2\. Compras  
	2.1. Compras con identificación de productos  
	2.2. Compras Genericas  
	2.3. Compras Automáticas (lectura de comprobantes PDF)  
	2.4. Listado de Saldos de Proveedores  
3\. Stock  
	3.1. Recepción de Productos  
	3.2. Remitos  
	3.3. Inventario  
4\. Tesorería  
	4.1. Recibos  
	4.2. Órdenes de Pago  
	4.3. Aplicación de Recibos y Ordenes de Pago  
	4.4. Listado de Recibos  
	4.5. Listado de Ordenes de Pago  
	4.6. Listado de Valores en Cartera  
	4.7. Listado de Cheques Emitidos  
	4.8. Capturas Homebanking  
	4.9. Conciliación Bancaria  
5\. Impuestos  
	5.1. Libro IVA Compras  
	5.2. Libro IVA Ventas  
	5.3. Capturas ARCA  
	5.4. Capturas Rentas / Convenio  
	5.5. Conciliaciones   
6\. Contabilidad  
5.1. Asientos Manuales  
5.2. Sumas y Saldos  
5.3. Mayor General  
5.4. Asientos Automáticos

\# Análisis Comparativo y Súper Prompt de Desarrollo — ERP Ikigai

Este documento presenta el análisis técnico del sistema contable y ERP heredado desarrollado en \*\*Visual FoxPro 9.0 (VFP)\*\* y su correspondencia con el nuevo sistema \*\*Django / PostgreSQL (ERP Ikigai)\*\* en \`d:\\jm\_soft\\erp-ikigai\`. Al final, se incluye el \*\*Súper Prompt\*\* diseñado para continuar con el desarrollo de forma estructurada.

\---

\#\# 1\. Arquitectura del Sistema: VFP 9.0 vs Django / PostgreSQL

La transición del sistema original a la web moderna implica un cambio fundamental en el diseño de los datos y su almacenamiento:

\`\`\`mermaid  
graph TD  
    subgraph VFP\_90 \["Estructura FoxPro 9.0 (Multi-Tenant por Carpetas)"\]  
        A\[Carpeta net\_balances\]  
        A \--\> B\[Eje\_001\_01 \- Carpeta Empresa 1 Ejercicio 1\]  
        A \--\> C\[Eje\_057\_02 \- Carpeta Empresa 57 Ejercicio 2\]  
        B \--\> D\[asiento.DBF / \*.CDX / \*.FPT\]  
        B \--\> E\[lib\_iva.DBF\]  
        B \--\> F\[cli\_pro.DBF\]  
    end

    subgraph Django\_Postgres \["Estructura Django / Postgres (Multi-Tenant por Filas)"\]  
        G\[(PostgreSQL DB única)\]  
        G \--\> H\[Tabla empresas\_empresa\]  
        G \--\> I\[Tabla empresas\_ejercicio\]  
        G \--\> J\[Tabla cble\_cuentas\]  
        G \--\> K\[Tabla facturacion\_clienteproveedor\]  
        G \--\> L\[Tabla facturacion\_venta\]  
          
        I \--\>|Filtro / Relación FK| J  
        H \--\>|Filtro / Relación FK| K  
        H \--\>|Filtro / Relación FK| L  
    end  
\`\`\`

\#\#\# Tabla de Correspondencia Técnica General

| Aspecto | Sistema Anterior (VFP 9.0) | Nuevo Sistema (Django/Postgres \- erp-ikigai) |  
| :--- | :--- | :--- |  
| \*\*Almacenamiento\*\* | Tablas DBF, archivos de índices CDX y campos memo FPT distribuidos. | Base de datos relacional PostgreSQL con almacenamiento centralizado. |  
| \*\*Multi-Empresa\*\* | Físico: Carpetas de red separadas (ej. \`Eje\_057\_01\`, \`Eje\_083\_03\`). | Lógico: Campo Foreign Key \`empresa\_id\` y \`ejercicio\_id\` en las tablas operativas. |  
| \*\*Ejercicios Fiscales\*\* | Definidos a nivel de carpetas y base central \`principal\!ejercicios\`. | Modelo \`Ejercicio\` (\`empresas\_ejercicio\`) con validación de no solapamiento. |  
| \*\*Vistas e Índices\*\* | Definidos en código PRG (ej. \`genera\_vista\_contable.prg\`) usando vistas SQL VFP. | Índices compuestos en Django (ej. \`\[empresa\_id, fecha\]\`) optimizados para Postgres. |  
| \*\*Motor de Consulta\*\* | Motor local de FoxPro (comando \`SELECT\` local y búferes locales). | QuerySet ORM de Django ejecutado en servidor Postgres, HTMX en frontend. |

\---

\#\# 2\. Mapeo de Modelos Contables y de Facturación

Basado en el análisis de \`genera\_vista\_contable.prg\` de VFP 9.0 y los modelos actuales de Django en \`facturacion/models.py\` y \`contable/models.py\`:

\#\#\# 2.1. Entidades de Cuentas y Asientos  
\* \*\*Cuentas (\`contable\!cuentas\` $\\rightarrow$ \`cble\_cuentas\`)\*\*:  
  \* VFP usa \`codigo\`, \`detalle\`, \`tipo\` (Activo, Pasivo, etc.).  
  \* Django utiliza el modelo \[Cuenta\](file:///d:/jm\_soft/erp-ikigai/contable/models.py\#L6-L39) (\`db\_table \= "cble\_cuentas"\`) con campos como \`jerarquia\`, \`cuenta\` (nombre), e \`imputable\` (0: No, 1: Sí).  
\* \*\*Asientos y Movimientos (\`contable\!asto\_enc\` / \`asto\_mov\` $\\rightarrow$ \`cble\_asiento\_enc\` / \`cble\_asiento\_mov\`)\*\*:  
  \* En VFP, \`asto\_enc\` tiene \`id\_asto\`, \`asiento\`, \`fecha\`, \`concepto\`, \`monto\` y \`id\_eje\_a\`.  
  \* En Django, se mapea para mantener la partida doble (Debe y Haber), relacionándolo con la cuenta contable de forma imputable.

\#\#\# 2.2. IVA y Comprobantes (\`contable\!lib\_iva\` $\\rightarrow$ \`facturacion\_libiva\`)  
\* El registro de IVA en VFP (\`lib\_iva\`) centraliza compras y ventas diferenciadas por el flag \`c\_v\` ('C' o 'V'). Contiene el detalle impositivo completo: \`neto\`, \`alic\_iva\`, \`iva\`, tasas específicas (\`itc\`, \`imp\_int\`), retenciones/percepciones (\`ret\_iva\`, \`ret\_gcia\`, \`ret\_ib\`, \`ret\_mun\`, \`sircreb\`), y datos de CAE (\`cae\`, \`vto\_cae\`, \`cod\_qr\`).  
\* En Django, las compras y ventas se registran de forma separada en \`Compra\` / \`CompraItem\` y \`Venta\` / \`VentaItem\`, alimentando mediante signals el modelo de trazabilidad \`Movimiento\` (tabla \`facturacion\_movimiento\`) y el futuro reporte de Libro IVA Digital.

\---

\#\# 3\. Mapeo de Módulos de Negocio (Verticales)

El sistema original en VFP 9.0 maneja múltiples rubros para sus clientes. Se han analizado las vistas de cada sector y su diseño correspondiente en Django:

\#\#\# 3.1. Armería (Weapons/Ammo)  
\* \*\*Contexto VFP\*\*: Tablas y pantallas de inventario de armas (\`inventario\_armas.scx\`).  
\* \*\*Diseño Django\*\*:  
  \* \*\*Clientes\*\*: \[ExtensionArmeria\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L123-L130) almacena la CLU (Credencial de Legítimo Usuario) y su fecha de vencimiento (\`clu\_vto\`).  
  \* \*\*Productos Individuales\*\*: El modelo \[Subproducto\](file:///d:/jm\_soft/erp-ikigai/productos/models.py\#L135-L178) maneja ítems únicos por número de \`serie\` y número de \`cuim\` (otorgado por ANMaC/ARCA) con trazabilidad de su costo de adquisición y cotización de venta.  
  \* \*\*Venta\*\*: \[VentaItem\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L267-L282) incluye campos específicos como \`credencial\` y \`dmp\` (Declaración de Municiones).

\#\#\# 3.2. Transporte (Freight/Logistics)  
\* \*\*Contexto VFP\*\*: Archivos \`genera\_vista\_transporte.prg\` y \`genera\_vista\_expresorivadavia.prg\`. Consultas de \`cons\_orden\_carga\` y \`repartos\`.  
\* \*\*Diseño Django\*\*: Requerirá la creación de los modelos \`OrdenCarga\`, \`Reparto\`, y \`LiquidacionChofer\`. Estos vincularán el comprobante (Factura o Remito) con la hoja de ruta y calcularán los fletes pendientes a pagar a los fleteros contratados o choferes propios.

\#\#\# 3.3. Colegio (IPJA \- Instituto Privado Joven Argentino)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_colegio.prg\`. CUIT exento \`30638118382\`.  
\* \*\*Diseño Django\*\*:  
  \* \*\*Clientes\*\*: El modelo \[ExtensionJosen\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L131-L138) define un \`coeficiente\` de descuento o recargo y lo asocia a un \[RubroJosen\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L32-L41).  
  \* \*\*Cobros\*\*: Lógica para facturación masiva de cuotas escolares mensuales con coeficientes variables por alumno.

\#\#\# 3.4. Estaciones de Servicio (GNC/Combustibles)  
\* \*\*Contexto VFP\*\*: Tablas \`gnc\_tot\_diario.dbf\`, \`gnc\_diario.dbf\`, \`gnc\_n.dbf\`, y proceso \`gnc\_captura.prg\`.  
\* \*\*Diseño Django\*\*: Requerirá modelos para controlar la planilla diaria de playa: lectura inicial y final de surtidores, cálculo de faltantes (\`gnc\_cons\_faltante\`), ventas en efectivo/tarjetas, y conciliación contra el inventario del tanque de combustible.

\#\#\# 3.5. Inmobiliaria (Real Estate)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_inmobiliaria.prg\` e \`inm\_aux\_vta.dbf\`.  
\* \*\*Diseño Django\*\*: Modelos para contratos de alquiler con indexación, control de vencimientos, cobro de alquileres a inquilinos y posterior liquidación a propietarios aplicando comisiones de administración.

\#\#\# 3.6. Peluquería (Hair Salon)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_peluqueria.prg\` y \`pelu\_cobro\_tarjetas\_aux.dbf\`.  
\* \*\*Diseño Django\*\*: Gestión de órdenes de trabajo diarias, turnos asignados a estilistas, cálculo de comisiones a los profesionales del salón y conciliación de cobros con tarjetas de crédito/débito.

\---

\#\# 4\. Reglas Críticas de Arquitectura en Django (Establecidas)

Para evitar duplicaciones y fugas de datos que ocurrían en el sistema VFP original, se establecen las siguientes directrices técnicas:

1\. \*\*Atomicidad Transaccional\*\*: El cálculo de saldos (\`ClienteProveedor.saldo\`) y el stock de los productos (\`StockSucursal.cantidad\`) debe ser atómico. Cualquier creación/modificación de ítems de compra/venta se encapsulará en \`transaction.atomic()\` a través de un único servicio centralizado.  
2\. \*\*Cálculo de Totales en el Modelo\*\*: Las cabeceras de compras y ventas no deben calcularse en los formularios. El método \`recalcular\_totales()\` del modelo debe sumar neto, alícuotas de IVA y percepciones a partir de los items guardados, gatillado por signals de Django.  
3\. \*\*Rol de \`Movimiento\`\*\*: El modelo \`Movimiento\` se asume como una \*\*vista materializada\*\* de lectura rápida para reportes impositivos e históricos. Se actualiza mediante signals \`post\_save\`/\`post\_delete\` de los comprobantes y no admite modificaciones directas del usuario.  
4\. \*\*Validaciones en el Modelo\*\*: Las validaciones complejas (como no solapamiento de fechas en ejercicios fiscales y clasificaciones correctas de clientes/proveedores) se realizan en el método \`clean()\` del modelo, garantizando su validez en cualquier flujo (admin, HTMX, shell o scripts de migración).

\---

\#\# 5\. EL SÚPER PROMPT

Copia y pega este prompt en el chat del asistente para guiar el desarrollo de cualquier nuevo módulo del ERP en Django.

\`\`\`markdown  
Actúa como un arquitecto y programador senior experto en Python, Django, PostgreSQL y HTMX.   
Estamos desarrollando un ERP modular multi-empresa llamado "ERP Ikigai" (localizado en d:\\jm\_soft\\erp-ikigai), el cual migra y unifica la lógica de un sistema heredado desarrollado en Visual FoxPro 9.0 (cuyos datos históricos están en d:\\jm\_soft\\net\_balances).

Debes seguir estrictamente las siguientes pautas de diseño y desarrollo en cada propuesta de código:

\#\#\# 1\. STACK TECNOLÓGICO Y DISEÑO  
\- Backend: Python 3.x, Django 5.x, PostgreSQL.  
\- Frontend: HTML Semántico, CSS Vanilla limpio con estética premium (gradientes modernos, modo oscuro/claro elegante, micro-animaciones en botones y transiciones suaves), y HTMX para interacciones dinámicas y modales asíncronos.  
\- Evita placeholders o código simulado. Todo el código propuesto debe ser 100% funcional.  
\- Mantén la integridad del código: conserva comentarios, docstrings y lógica previa no relacionada al cambio. Comenta en detalle la lógica detrás de tus modificaciones en Español.

\#\#\# 2\. ESTRUCTURA DE BASE DE DATOS Y MULTI-TENANCY (Logical vs Physical)  
\- El sistema heredado en VFP usaba multi-tenant físico (carpetas separadas como Eje\_057\_01 para cada empresa y año).  
\- ERP Ikigai usa multi-tenant lógico por filas en una base de datos PostgreSQL única.  
\- Todas las tablas principales (Compras, Ventas, Cuentas, etc.) se vinculan a la empresa mediante ForeignKey a \`empresas.Empresa\` y al año fiscal activo mediante ForeignKey a \`empresas.Ejercicio\`.  
\- Las búsquedas e informes siempre deben filtrar primero por la empresa activa y por el ejercicio activo para garantizar el rendimiento.

\#\#\# 3\. REGLAS CRÍTICAS DE TRANSACCIONALIDAD E INTEGRIDAD  
\- \*\*Atomicidad de Saldos\*\*: Los saldos de clientes y proveedores se calculan en un servicio centralizado ('contable/services/saldos.py') usando transaction.atomic(). No se asigna saldo directamente en las vistas.  
\- \*\*Cálculo de Stock\*\*: El stock de productos se actualiza exclusivamente mediante signals (post\_save/post\_delete) sobre items de comprobante, calculando los deltas con pre\_save para evitar duplicaciones.  
\- \*\*Totales de Cabecera\*\*: El neto, IVA y total general de facturas/compras se calculan en métodos del modelo ('recalcular\_totales()') invocados desde los items, no en formularios HTML.  
\- \*\*El Modelo Movimiento\*\*: 'Movimiento' actúa como una vista materializada automatizada (Kardex de auditoría) sincronizada por signals de compras y ventas.

\#\#\# 4\. MÓDULOS DE NEGOCIO VERTICALES A SOPORTAR  
Al diseñar nuevos flujos o campos, ten en cuenta la especialización del cliente según su CUIT:  
\- \*\*Armería (Weapons)\*\*: Control de CLU y vencimiento en 'ExtensionArmeria'. Trazabilidad física de unidades individuales mediante el modelo 'Subproducto' (serie, CUIM, estado nuevo/usado, propiedad propia/consignada). Facturación con campos credencial y DMP en 'VentaItem'.  
\- \*\*Transporte (Freight)\*\*: Gestión de fletes, hojas de ruta (Repartos), liquidación a choferes y órdenes de carga.  
\- \*\*Colegio (Education)\*\*: Coeficientes de descuento/recargo para alumnos en 'ExtensionJosen' y facturación masiva.  
\- \*\*GNC (Gas Stations)\*\*: Cierre de turnos de surtidores, planilla de playa y auditoría de faltantes de combustible.  
\- \*\*Inmobiliaria (Real Estate)\*\*: Contratos de alquiler, indexación mensual de montos, cobros y comisiones.  
\- \*\*Peluquería (Salon)\*\*: Turnos de estilistas, comisiones por servicio y conciliación de liquidaciones de tarjetas.

\#\#\# TAREA ACTUAL  
\[INSERTAR AQUÍ LA TAREA ESPECÍFICA A REALIZAR, POR EJEMPLO: "Implementar el módulo de Recibos de Cobro y Órdenes de Pago vinculados a facturas, asegurando actualizar los saldos a través del servicio de saldos atómico."\]

Por favor, analiza el código actual de la aplicación antes de proponer cambios, respetando la nomenclatura existente de variables, bases de datos y la codificación anterior para permitir un rollback limpio si es necesario. Responde siempre en Español.  
\`\`\`

\---

\#\# 6\. Siguientes Pasos Recomendados

Para continuar con el desarrollo de forma sólida, se aconseja:  
1\. \*\*Implementar las Mejoras de Prioridad 1 y 2\*\*: Completar el servicio centralizado de saldos atómicos y añadir los tests automatizados para asegurar la base transaccional antes de agregar nuevos módulos.  
2\. \*\*Crear Scripts de Migración Seguros\*\*: Utilizar la biblioteca \`dbfread\` de Python para extraer datos históricos de las carpetas \`Eje\_XXX\` de VFP y subirlos a la base PostgreSQL de Django de forma automatizada por lotes.  
3\. \*\*Consolidar los Módulos Verticales\*\*: Diseñar las vistas y formularios HTMX para Armería (Subproductos por número de serie) y Colegio (coeficientes automatizados), que son los módulos prioritarios en la configuración actual.

\# Análisis Comparativo y Súper Prompt de Desarrollo — ERP Ikigai

Este documento presenta el análisis técnico del sistema contable y ERP heredado desarrollado en \*\*Visual FoxPro 9.0 (VFP)\*\* y su correspondencia con el nuevo sistema \*\*Django / PostgreSQL (ERP Ikigai)\*\* en \`d:\\jm\_soft\\erp-ikigai\`. Al final, se incluye el \*\*Súper Prompt\*\* diseñado para continuar con el desarrollo de forma estructurada.

\---

\#\# 1\. Arquitectura del Sistema: VFP 9.0 vs Django / PostgreSQL

La transición del sistema original a la web moderna implica un cambio fundamental en el diseño de los datos y su almacenamiento:

\`\`\`mermaid  
graph TD  
    subgraph VFP\_90 \["Estructura FoxPro 9.0 (Multi-Tenant por Carpetas)"\]  
        A\[Carpeta net\_balances\]  
        A \--\> B\[Eje\_001\_01 \- Carpeta Empresa 1 Ejercicio 1\]  
        A \--\> C\[Eje\_057\_02 \- Carpeta Empresa 57 Ejercicio 2\]  
        B \--\> D\[asiento.DBF / \*.CDX / \*.FPT\]  
        B \--\> E\[lib\_iva.DBF\]  
        B \--\> F\[cli\_pro.DBF\]  
    end

    subgraph Django\_Postgres \["Estructura Django / Postgres (Multi-Tenant por Filas)"\]  
        G\[(PostgreSQL DB única)\]  
        G \--\> H\[Tabla empresas\_empresa\]  
        G \--\> I\[Tabla empresas\_ejercicio\]  
        G \--\> J\[Tabla cble\_cuentas\]  
        G \--\> K\[Tabla facturacion\_clienteproveedor\]  
        G \--\> L\[Tabla facturacion\_venta\]  
          
        I \--\>|Filtro / Relación FK| J  
        H \--\>|Filtro / Relación FK| K  
        H \--\>|Filtro / Relación FK| L  
    end  
\`\`\`

\#\#\# Tabla de Correspondencia Técnica General

| Aspecto | Sistema Anterior (VFP 9.0) | Nuevo Sistema (Django/Postgres \- erp-ikigai) |  
| :--- | :--- | :--- |  
| \*\*Almacenamiento\*\* | Tablas DBF, archivos de índices CDX y campos memo FPT distribuidos. | Base de datos relacional PostgreSQL con almacenamiento centralizado. |  
| \*\*Multi-Empresa\*\* | Físico: Carpetas de red separadas (ej. \`Eje\_057\_01\`, \`Eje\_083\_03\`). | Lógico: Campo Foreign Key \`empresa\_id\` y \`ejercicio\_id\` en las tablas operativas. |  
| \*\*Ejercicios Fiscales\*\* | Definidos a nivel de carpetas y base central \`principal\!ejercicios\`. | Modelo \`Ejercicio\` (\`empresas\_ejercicio\`) con validación de no solapamiento. |  
| \*\*Vistas e Índices\*\* | Definidos en código PRG (ej. \`genera\_vista\_contable.prg\`) usando vistas SQL VFP. | Índices compuestos en Django (ej. \`\[empresa\_id, fecha\]\`) optimizados para Postgres. |  
| \*\*Motor de Consulta\*\* | Motor local de FoxPro (comando \`SELECT\` local y búferes locales). | QuerySet ORM de Django ejecutado en servidor Postgres, HTMX en frontend. |

\---

\#\# 2\. Mapeo de Modelos Contables y de Facturación

Basado en el análisis de \`genera\_vista\_contable.prg\` de VFP 9.0 y los modelos actuales de Django en \`facturacion/models.py\` y \`contable/models.py\`:

\#\#\# 2.1. Entidades de Cuentas y Asientos  
\* \*\*Cuentas (\`contable\!cuentas\` $\\rightarrow$ \`cble\_cuentas\`)\*\*:  
  \* VFP usa \`codigo\`, \`detalle\`, \`tipo\` (Activo, Pasivo, etc.).  
  \* Django utiliza el modelo \[Cuenta\](file:///d:/jm\_soft/erp-ikigai/contable/models.py\#L6-L39) (\`db\_table \= "cble\_cuentas"\`) con campos como \`jerarquia\`, \`cuenta\` (nombre), e \`imputable\` (0: No, 1: Sí).  
\* \*\*Asientos y Movimientos (\`contable\!asto\_enc\` / \`asto\_mov\` $\\rightarrow$ \`cble\_asiento\_enc\` / \`cble\_asiento\_mov\`)\*\*:  
  \* En VFP, \`asto\_enc\` tiene \`id\_asto\`, \`asiento\`, \`fecha\`, \`concepto\`, \`monto\` y \`id\_eje\_a\`.  
  \* En Django, se mapea para mantener la partida doble (Debe y Haber), relacionándolo con la cuenta contable de forma imputable.

\#\#\# 2.2. IVA y Comprobantes (\`contable\!lib\_iva\` $\\rightarrow$ \`facturacion\_libiva\`)  
\* El registro de IVA en VFP (\`lib\_iva\`) centraliza compras y ventas diferenciadas por el flag \`c\_v\` ('C' o 'V'). Contiene el detalle impositivo completo: \`neto\`, \`alic\_iva\`, \`iva\`, tasas específicas (\`itc\`, \`imp\_int\`), retenciones/percepciones (\`ret\_iva\`, \`ret\_gcia\`, \`ret\_ib\`, \`ret\_mun\`, \`sircreb\`), y datos de CAE (\`cae\`, \`vto\_cae\`, \`cod\_qr\`).  
\* En Django, las compras y ventas se registran de forma separada en \`Compra\` / \`CompraItem\` y \`Venta\` / \`VentaItem\`, alimentando mediante signals el modelo de trazabilidad \`Movimiento\` (tabla \`facturacion\_movimiento\`) y el futuro reporte de Libro IVA Digital.

\---

\#\# 3\. Mapeo de Módulos de Negocio (Verticales)

El sistema original en VFP 9.0 maneja múltiples rubros para sus clientes. Se han analizado las vistas de cada sector y su diseño correspondiente en Django:

\#\#\# 3.1. Armería (Weapons/Ammo)  
\* \*\*Contexto VFP\*\*: Tablas y pantallas de inventario de armas (\`inventario\_armas.scx\`).  
\* \*\*Diseño Django\*\*:  
  \* \*\*Clientes\*\*: \[ExtensionArmeria\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L123-L130) almacena la CLU (Credencial de Legítimo Usuario) y su fecha de vencimiento (\`clu\_vto\`).  
  \* \*\*Productos Individuales\*\*: El modelo \[Subproducto\](file:///d:/jm\_soft/erp-ikigai/productos/models.py\#L135-L178) maneja ítems únicos por número de \`serie\` y número de \`cuim\` (otorgado por ANMaC/ARCA) con trazabilidad de su costo de adquisición y cotización de venta.  
  \* \*\*Venta\*\*: \[VentaItem\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L267-L282) incluye campos específicos como \`credencial\` y \`dmp\` (Declaración de Municiones).

\#\#\# 3.2. Transporte (Freight/Logistics)  
\* \*\*Contexto VFP\*\*: Archivos \`genera\_vista\_transporte.prg\` y \`genera\_vista\_expresorivadavia.prg\`. Consultas de \`cons\_orden\_carga\` y \`repartos\`.  
\* \*\*Diseño Django\*\*: Requerirá la creación de los modelos \`OrdenCarga\`, \`Reparto\`, y \`LiquidacionChofer\`. Estos vincularán el comprobante (Factura o Remito) con la hoja de ruta y calcularán los fletes pendientes a pagar a los fleteros contratados o choferes propios.

\#\#\# 3.3. Colegio (IPJA \- Instituto Privado Joven Argentino)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_colegio.prg\`. CUIT exento \`30638118382\`.  
\* \*\*Diseño Django\*\*:  
  \* \*\*Clientes\*\*: El modelo \[ExtensionJosen\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L131-L138) define un \`coeficiente\` de descuento o recargo y lo asocia a un \[RubroJosen\](file:///d:/jm\_soft/erp-ikigai/facturacion/models.py\#L32-L41).  
  \* \*\*Cobros\*\*: Lógica para facturación masiva de cuotas escolares mensuales con coeficientes variables por alumno.

\#\#\# 3.4. Estaciones de Servicio (GNC/Combustibles)  
\* \*\*Contexto VFP\*\*: Tablas \`gnc\_tot\_diario.dbf\`, \`gnc\_diario.dbf\`, \`gnc\_n.dbf\`, y proceso \`gnc\_captura.prg\`.  
\* \*\*Diseño Django\*\*: Requerirá modelos para controlar la planilla diaria de playa: lectura inicial y final de surtidores, cálculo de faltantes (\`gnc\_cons\_faltante\`), ventas en efectivo/tarjetas, y conciliación contra el inventario del tanque de combustible.

\#\#\# 3.5. Inmobiliaria (Real Estate)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_inmobiliaria.prg\` e \`inm\_aux\_vta.dbf\`.  
\* \*\*Diseño Django\*\*: Modelos para contratos de alquiler con indexación, control de vencimientos, cobro de alquileres a inquilinos y posterior liquidación a propietarios aplicando comisiones de administración.

\#\#\# 3.6. Peluquería (Hair Salon)  
\* \*\*Contexto VFP\*\*: \`genera\_vista\_peluqueria.prg\` y \`pelu\_cobro\_tarjetas\_aux.dbf\`.  
\* \*\*Diseño Django\*\*: Gestión de órdenes de trabajo diarias, turnos asignados a estilistas, cálculo de comisiones a los profesionales del salón y conciliación de cobros con tarjetas de crédito/débito.

\---

\#\# 4\. Reglas Críticas de Arquitectura en Django (Establecidas)

Para evitar duplicaciones y fugas de datos que ocurrían en el sistema VFP original, se establecen las siguientes directrices técnicas:

1\. \*\*Atomicidad Transaccional\*\*: El cálculo de saldos (\`ClienteProveedor.saldo\`) y el stock de los productos (\`StockSucursal.cantidad\`) debe ser atómico. Cualquier creación/modificación de ítems de compra/venta se encapsulará en \`transaction.atomic()\` a través de un único servicio centralizado.  
2\. \*\*Cálculo de Totales en el Modelo\*\*: Las cabeceras de compras y ventas no deben calcularse en los formularios. El método \`recalcular\_totales()\` del modelo debe sumar neto, alícuotas de IVA y percepciones a partir de los items guardados, gatillado por signals de Django.  
3\. \*\*Rol de \`Movimiento\`\*\*: El modelo \`Movimiento\` se asume como una \*\*vista materializada\*\* de lectura rápida para reportes impositivos e históricos. Se actualiza mediante signals \`post\_save\`/\`post\_delete\` de los comprobantes y no admite modificaciones directas del usuario.  
4\. \*\*Validaciones en el Modelo\*\*: Las validaciones complejas (como no solapamiento de fechas en ejercicios fiscales y clasificaciones correctas de clientes/proveedores) se realizan en el método \`clean()\` del modelo, garantizando su validez en cualquier flujo (admin, HTMX, shell o scripts de migración).

\---

\#\# 5\. EL SÚPER PROMPT

Copia y pega este prompt en el chat del asistente para guiar el desarrollo de cualquier nuevo módulo del ERP en Django.

\`\`\`markdown  
Actúa como un arquitecto y programador senior experto en Python, Django, PostgreSQL y HTMX.   
Estamos desarrollando un ERP modular multi-empresa llamado "ERP Ikigai" (localizado en d:\\jm\_soft\\erp-ikigai), el cual migra y unifica la lógica de un sistema heredado desarrollado en Visual FoxPro 9.0 (cuyos datos históricos están en d:\\jm\_soft\\net\_balances).

Debes seguir estrictamente las siguientes pautas de diseño y desarrollo en cada propuesta de código:

\#\#\# 1\. STACK TECNOLÓGICO Y DISEÑO  
\- Backend: Python 3.x, Django 5.x, PostgreSQL.  
\- Frontend: HTML Semántico, CSS Vanilla limpio con estética premium (gradientes modernos, modo oscuro/claro elegante, micro-animaciones en botones y transiciones suaves), y HTMX para interacciones dinámicas y modales asíncronos.  
\- Evita placeholders o código simulado. Todo el código propuesto debe ser 100% funcional.  
\- Mantén la integridad del código: conserva comentarios, docstrings y lógica previa no relacionada al cambio. Comenta en detalle la lógica detrás de tus modificaciones en Español.

\#\#\# 2\. ESTRUCTURA DE BASE DE DATOS Y MULTI-TENANCY (Logical vs Physical)  
\- El sistema heredado en VFP usaba multi-tenant físico (carpetas separadas como Eje\_057\_01 para cada empresa y año).  
\- ERP Ikigai usa multi-tenant lógico por filas en una base de datos PostgreSQL única.  
\- Todas las tablas principales (Compras, Ventas, Cuentas, etc.) se vinculan a la empresa mediante ForeignKey a \`empresas.Empresa\` y al año fiscal activo mediante ForeignKey a \`empresas.Ejercicio\`.  
\- Las búsquedas e informes siempre deben filtrar primero por la empresa activa y por el ejercicio activo para garantizar el rendimiento.

\#\#\# 3\. REGLAS CRÍTICAS DE TRANSACCIONALIDAD E INTEGRIDAD  
\- \*\*Atomicidad de Saldos\*\*: Los saldos de clientes y proveedores se calculan en un servicio centralizado ('contable/services/saldos.py') usando transaction.atomic(). No se asigna saldo directamente en las vistas.  
\- \*\*Cálculo de Stock\*\*: El stock de productos se actualiza exclusivamente mediante signals (post\_save/post\_delete) sobre items de comprobante, calculando los deltas con pre\_save para evitar duplicaciones.  
\- \*\*Totales de Cabecera\*\*: El neto, IVA y total general de facturas/compras se calculan en métodos del modelo ('recalcular\_totales()') invocados desde los items, no en formularios HTML.  
\- \*\*El Modelo Movimiento\*\*: 'Movimiento' actúa como una vista materializada automatizada (Kardex de auditoría) sincronizada por signals de compras y ventas.

\#\#\# 4\. MÓDULOS DE NEGOCIO VERTICALES A SOPORTAR  
Al diseñar nuevos flujos o campos, ten en cuenta la especialización del cliente según su CUIT:  
\- \*\*Armería (Weapons)\*\*: Control de CLU y vencimiento en 'ExtensionArmeria'. Trazabilidad física de unidades individuales mediante el modelo 'Subproducto' (serie, CUIM, estado nuevo/usado, propiedad propia/consignada). Facturación con campos credencial y DMP en 'VentaItem'.  
\- \*\*Transporte (Freight)\*\*: Gestión de fletes, hojas de ruta (Repartos), liquidación a choferes y órdenes de carga.  
\- \*\*Colegio (Education)\*\*: Coeficientes de descuento/recargo para alumnos en 'ExtensionJosen' y facturación masiva.  
\- \*\*GNC (Gas Stations)\*\*: Cierre de turnos de surtidores, planilla de playa y auditoría de faltantes de combustible.  
\- \*\*Inmobiliaria (Real Estate)\*\*: Contratos de alquiler, indexación mensual de montos, cobros y comisiones.  
\- \*\*Peluquería (Salon)\*\*: Turnos de estilistas, comisiones por servicio y conciliación de liquidaciones de tarjetas.

\#\#\# TAREA ACTUAL  
\[INSERTAR AQUÍ LA TAREA ESPECÍFICA A REALIZAR, POR EJEMPLO: "Implementar el módulo de Recibos de Cobro y Órdenes de Pago vinculados a facturas, asegurando actualizar los saldos a través del servicio de saldos atómico."\]

Por favor, analiza el código actual de la aplicación antes de proponer cambios, respetando la nomenclatura existente de variables, bases de datos y la codificación anterior para permitir un rollback limpio si es necesario. Responde siempre en Español.  
\`\`\`

\---

\#\# 6\. Siguientes Pasos Recomendados

Para continuar con el desarrollo de forma sólida, se aconseja:  
1\. \*\*Implementar las Mejoras de Prioridad 1 y 2\*\*: Completar el servicio centralizado de saldos atómicos y añadir los tests automatizados para asegurar la base transaccional antes de agregar nuevos módulos.  
2\. \*\*Crear Scripts de Migración Seguros\*\*: Utilizar la biblioteca \`dbfread\` de Python para extraer datos históricos de las carpetas \`Eje\_XXX\` de VFP y subirlos a la base PostgreSQL de Django de forma automatizada por lotes.  
3\. \*\*Consolidar los Módulos Verticales\*\*: Diseñar las vistas y formularios HTMX para Armería (Subproductos por número de serie) y Colegio (coeficientes automatizados), que son los módulos prioritarios en la configuración actual.

