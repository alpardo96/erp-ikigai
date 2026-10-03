# erp-ikigai-2

Este es el repositorio del proyecto ERP Ikigai 2.

## Configuración y vinculación inicial

Este repositorio ha sido inicializado y vinculado con GitHub mediante Git.

## Requisitos de Inicialización y Configuración

Durante la instalación inicial o despliegue en un nuevo cliente, se deben dar de alta obligatoriamente los siguientes **Productos (Tipo Servicio/Gasto)** en el módulo de Inventario/Productos para que el flujo automático de rechazo de Valores de Terceros en Tesorería funcione correctamente:

1. **CHEQUE RECHAZADO**: 
   - **Uso**: Generación automática de la Nota de Débito Interna (DI) al cliente (por el valor original del cheque) y el Comprobante Interno de Compra (CI) de reversión para el proveedor.
   - **Detalle recomendado**: `CHEQUE RECHAZADO`
   - **Rubro**: `RECUPERO DE GASTOS` (o similar)
   - **Precios**: `$0,00` (el sistema lo inyecta dinámicamente)

2. **GASTO CHEQUE RECHAZADO**:
   - **Uso**: Generación de la Nota de Débito (Fiscal ND A/B, o NDI Presupuestada) por los gastos bancarios y penalidades de rechazo que se le cobran al cliente.
   - **Detalle recomendado**: `GASTO CHEQUE RECHAZADO`
   - **Rubro**: `RECUPERO DE GASTOS` (o similar)
   - **Precios**: `$0,00` (el usuario lo define en el modal al rechazar)
