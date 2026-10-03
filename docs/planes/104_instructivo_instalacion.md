# Plan: Instructivo de Instalación y Configuración Inicial

Este documento se genera a pedido del usuario para agendar y estructurar la creación de un **Manual de Instalación y Configuración Inicial** del ERP Ikigai.

## Objetivos del Manual
- Guiar a un implementador desde el despliegue del código hasta el sistema funcional.
- Documentar todas las parametrizaciones requeridas por la base de datos que no están resueltas únicamente con las migraciones, sino que dependen de "carga de datos semilla" (seed data).

## Estructura Propuesta

1. **Requisitos del Sistema**
   - Base de Datos (PostgreSQL)
   - Python y Dependencias
   - Redis/Celery (si aplica)

2. **Despliegue Técnico**
   - Clonado del repositorio
   - Creación del entorno virtual
   - Ejecución de `python manage.py migrate`

3. **Carga Inicial de Maestros y Parámetros (Data Entry / Seed)**
   - **Empresas y Sucursales**: Creación de la empresa principal y la sucursal por defecto.
   - **Usuarios y Permisos**: Creación del superusuario y asignación de permisos básicos.
   - **Productos Comodín (Servicios/Gastos Internos)**:
     - `CHEQUE RECHAZADO` (Requerido para procesos de Tesorería)
     - `GASTO CHEQUE RECHAZADO` (Requerido para Notas de Débito)
   - **Tipos de Comprobantes**: Asegurar la existencia de Facturas, Notas de Crédito, Notas de Débito, Recibos, OPs, Comprobantes Internos (CI/DI).
   - **Cuentas Contables y Plan de Cuentas**: Generación de las cuentas estructuradas mínimas.
   - **Bancos y Cuentas Bancarias**: Altas necesarias.

4. **Variables de Entorno (.env)**
   - Conexiones de Base de Datos.
   - Certificados de AFIP (WSFE/WSFEv1) y claves de homologación/producción.

## Próximos Pasos
- Completar cada sección de este documento con el detalle técnico paso a paso.
- Redactar un script automatizado `python manage.py setup_inicial` que se encargue de inyectar los tipos de comprobantes y productos comodín (como `CHEQUE RECHAZADO`) para evitar depender exclusivamente de la carga manual del implementador.
