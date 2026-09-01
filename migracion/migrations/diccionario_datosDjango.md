---
RequestFeedback: false
Summary: Diccionario de datos agrupado por aplicación y tabla.
UserFacing: true
---

# Diccionario de Datos - PostgreSQL (Ikigai ERP 2)

Este documento detalla la estructura de la base de datos destino, agrupada por módulo (App) y Tabla, para facilitar el cruce con el esquema Legacy.

## Módulo: `EMPRESAS`

### Tabla: `Empresa`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **contadores** | ForeignKey | Sí | - |
| **usuarios** | ManyToManyField | Sí | - |
| **sucursales** | ForeignKey | Sí | - |
| **puntos_venta** | ForeignKey | Sí | - |
| **ejercicios** | ForeignKey | Sí | - |
| **cotizacion_moneda** | OneToOneField | Sí | - |
| **config_trazabilidad** | OneToOneField | Sí | - |
| **cuenta** | ForeignKey | Sí | - |
| **asiento** | ForeignKey | Sí | - |
| **parametroscontables** | OneToOneField | Sí | - |
| **libroivacompras** | ForeignKey | Sí | - |
| **libroivaventas** | ForeignKey | Sí | - |
| **retpercsufrida** | ForeignKey | Sí | - |
| **retencionpracticada** | ForeignKey | Sí | - |
| **marca** | ForeignKey | Sí | - |
| **rubro** | ForeignKey | Sí | - |
| **familia** | ForeignKey | Sí | - |
| **producto** | ForeignKey | Sí | - |
| **subproductos** | ForeignKey | Sí | - |
| **clienteproveedor** | ForeignKey | Sí | - |
| **tarifaestudio** | ForeignKey | Sí | - |
| **compra** | ForeignKey | Sí | - |
| **preventa** | ForeignKey | Sí | - |
| **venta** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **ordenes_compra** | ForeignKey | Sí | - |
| **recepciones** | ForeignKey | Sí | - |
| **remitos_internos** | ForeignKey | Sí | - |
| **mediopago** | ForeignKey | Sí | - |
| **cuentabancaria** | ForeignKey | Sí | - |
| **recibo** | ForeignKey | Sí | - |
| **ordenpago** | ForeignKey | Sí | - |
| **caja** | ForeignKey | Sí | - |
| **transaccionbancaria** | ForeignKey | Sí | - |
| **valorterceros** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **nombre** | CharField | No | - |
| **cuit** | CharField | No | - |
| **logo** | FileField | Sí | - |
| **direccion** | CharField | Sí | - |
| **correo** | CharField | Sí | - |
| **tipo_actividad** | CharField | Sí | - |
| **pedir_fecha_nacimiento_cliente** | BooleanField | No | - |
| **usa_orden_compra** | BooleanField | No | - |
| **usa_trazabilidad** | BooleanField | No | - |
| **condicion_iibb** | CharField | No | - |
| **entorno_afip** | CharField | No | - |
| **crt_afip** | FileField | Sí | - |
| **key_afip** | FileField | Sí | - |
| **jurisdicciones_iibb** | ManyToManyField | No | - |

### Tabla: `Sucursal`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **puntos_venta** | ForeignKey | Sí | - |
| **asiento** | ForeignKey | Sí | - |
| **marcas_disponibles** | ManyToManyField | Sí | - |
| **rubros_disponibles** | ManyToManyField | Sí | - |
| **familias_disponibles** | ManyToManyField | Sí | - |
| **stock_productos** | ForeignKey | Sí | - |
| **subproductos** | ForeignKey | Sí | - |
| **movimientostock** | ForeignKey | Sí | - |
| **compra** | ForeignKey | Sí | - |
| **preventa** | ForeignKey | Sí | - |
| **venta** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **ordenes_compra** | ForeignKey | Sí | - |
| **recepciones** | ForeignKey | Sí | - |
| **remitos_internos_emitidos** | ForeignKey | Sí | - |
| **remitos_internos_recibidos** | ForeignKey | Sí | - |
| **recibo** | ForeignKey | Sí | - |
| **ordenpago** | ForeignKey | Sí | - |
| **caja** | ForeignKey | Sí | - |
| **retiros_enviados** | ForeignKey | Sí | - |
| **retiros_recibidos** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **nombre** | CharField | No | - |
| **direccion** | CharField | Sí | - |
| **telefono** | CharField | Sí | - |
| **punto** | IntegerField | No | - |

### Tabla: `PuntoVenta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **numero** | IntegerField | No | - |
| **activo** | BooleanField | No | - |
| **caja_mostrador_default** | BooleanField | No | - |

### Tabla: `Ejercicio`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **asiento** | ForeignKey | Sí | - |
| **compra** | ForeignKey | Sí | - |
| **venta** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **recibo** | ForeignKey | Sí | - |
| **ordenpago** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **ejercicio** | CharField | No | - |
| **inicio** | DateField | No | - |
| **cierre** | DateField | No | - |

### Tabla: `CotizacionMoneda`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | OneToOneField | No | - |
| **dolar_venta** | DecimalField | No | - |
| **dolar_cobranza** | DecimalField | No | - |

### Tabla: `EmpresaTrazabilidad`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | OneToOneField | No | - |
| **pedir_situacion** | BooleanField | No | - |
| **pedir_estado** | BooleanField | No | - |
| **pedir_cuim** | BooleanField | No | - |

## Módulo: `USUARIOS`

### Tabla: `Perfil`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **usuario** | OneToOneField | No | - |
| **es_admin_sistema** | BooleanField | No | - |
| **permiso_clientes_ver** | BooleanField | No | - |
| **permiso_clientes_editar** | BooleanField | No | - |
| **permiso_armeria_ver** | BooleanField | No | - |
| **permiso_armeria_editar** | BooleanField | No | - |
| **permiso_josen_ver** | BooleanField | No | - |
| **permiso_josen_editar** | BooleanField | No | - |
| **permiso_facturacion_compras** | BooleanField | No | - |
| **permiso_facturacion_lista_compras** | BooleanField | No | - |
| **permiso_facturacion_autorizaciones** | BooleanField | No | - |
| **permiso_facturacion_carga_ventas** | BooleanField | No | - |
| **permiso_facturacion_lista_ventas** | BooleanField | No | - |
| **permiso_autorizar_descuentos** | BooleanField | No | - |
| **permiso_cotizaciones_editar** | BooleanField | No | - |
| **empresas** | ManyToManyField | No | - |

## Módulo: `PRODUCTOS`

### Tabla: `Marca`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **producto** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **detalle** | CharField | No | - |
| **margen** | DecimalField | No | - |
| **codigo_anterior** | CharField | Sí | - |
| **sucursales** | ManyToManyField | No | - |

### Tabla: `Rubro`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **familias** | ForeignKey | Sí | - |
| **producto** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **detalle** | CharField | No | - |
| **margen** | DecimalField | No | - |
| **descuento_maximo** | DecimalField | No | - |
| **codigo_anterior** | CharField | Sí | - |
| **cta_ventas** | ForeignKey | Sí | Cuenta |
| **cta_compras** | ForeignKey | Sí | Cuenta |
| **sucursales** | ManyToManyField | No | - |

### Tabla: `Familia`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **producto** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **detalle** | CharField | No | - |
| **margen** | DecimalField | No | - |
| **rubro** | ForeignKey | Sí | Rubro |
| **codigo_anterior** | CharField | Sí | - |
| **sucursales** | ManyToManyField | No | - |

### Tabla: `Producto`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **existencias** | ForeignKey | Sí | - |
| **subproductos** | ForeignKey | Sí | - |
| **movimientostock** | ForeignKey | Sí | - |
| **tarifaestudio** | ForeignKey | Sí | - |
| **compraitem** | ForeignKey | Sí | - |
| **preventaitem** | ForeignKey | Sí | - |
| **ventaitem** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **ordencompraitem** | ForeignKey | Sí | - |
| **recepcionitem** | ForeignKey | Sí | - |
| **remitointernoitem** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **cod_prov** | CharField | Sí | - |
| **cod_fab** | CharField | Sí | - |
| **detalle** | CharField | No | - |
| **proveedor** | ForeignKey | Sí | ClienteProveedor |
| **minimo** | DecimalField | No | - |
| **ptopedir** | DecimalField | No | - |
| **creden** | BooleanField | No | - |
| **moneda** | CharField | No | - |
| **alic_iva** | DecimalField | No | - |
| **marca** | ForeignKey | Sí | Marca |
| **rubro** | ForeignKey | Sí | Rubro |
| **familia** | ForeignKey | Sí | Familia |
| **subprod** | BooleanField | No | - |
| **stock** | DecimalField | No | - |
| **stkcons** | DecimalField | No | - |
| **compra_id** | IntegerField | Sí | - |
| **cto_adq** | DecimalField | No | - |
| **fec_adq** | DateField | Sí | - |
| **cto_rep** | DecimalField | No | - |
| **fec_act** | DateField | Sí | - |
| **margen** | DecimalField | No | - |
| **precio_neto** | DecimalField | No | - |
| **precio_total** | DecimalField | No | - |
| **cotiz_cpra** | DecimalField | No | - |

### Tabla: `StockSucursal`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **producto** | ForeignKey | No | Producto |
| **sucursal** | ForeignKey | No | Sucursal |
| **cantidad** | DecimalField | No | - |

### Tabla: `Subproducto`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **subpro** | AutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **producto** | ForeignKey | No | Producto |
| **sucursal** | ForeignKey | No | Sucursal |
| **serie** | CharField | No | - |
| **cuim** | CharField | Sí | - |
| **compra** | ForeignKey | Sí | Compra |
| **feccpra** | DateField | No | - |
| **cto_adq** | DecimalField | No | - |
| **cotizadq** | DecimalField | No | - |
| **moneda** | CharField | No | - |
| **alic_iva** | DecimalField | No | - |
| **margen** | DecimalField | No | - |
| **venta** | ForeignKey | Sí | Venta |
| **fecvta** | DateField | Sí | - |
| **precio_neto** | DecimalField | No | - |
| **precio_total** | DecimalField | No | - |
| **cotizvta** | DecimalField | No | - |
| **fecent** | DateField | Sí | - |
| **estado** | CharField | No | - |
| **propiedad** | CharField | No | - |
| **situacion** | CharField | No | - |

### Tabla: `MovimientoStock`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **producto** | ForeignKey | No | Producto |
| **sucursal** | ForeignKey | No | Sucursal |
| **tipo** | CharField | No | - |
| **cantidad** | DecimalField | No | - |
| **observacion** | TextField | Sí | - |

## Módulo: `FACTURACION`

### Tabla: `TipoComprobante`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **compra** | ForeignKey | Sí | - |
| **venta** | ForeignKey | Sí | - |
| **id** | AutoField | No | - |
| **codigo** | CharField | No | - |
| **detalle** | CharField | No | - |
| **signo** | SmallIntegerField | No | - |
| **estado** | BooleanField | No | - |

### Tabla: `Jurisdiccion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **empresas** | ManyToManyField | Sí | - |
| **retpercsufrida** | ForeignKey | Sí | - |
| **clienteproveedor** | ForeignKey | Sí | - |
| **compraretperc** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **codigo** | IntegerField | No | - |
| **nombre** | CharField | No | - |

### Tabla: `RubroJosen`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **extensionjosen** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **nombre** | CharField | No | - |

### Tabla: `ClienteProveedor`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **asiento** | ForeignKey | Sí | - |
| **asientolinea** | ForeignKey | Sí | - |
| **libroivacompras** | ForeignKey | Sí | - |
| **libroivaventas** | ForeignKey | Sí | - |
| **retencionpracticada** | ForeignKey | Sí | - |
| **productos_provistos** | ForeignKey | Sí | - |
| **armeria** | OneToOneField | Sí | - |
| **josen** | OneToOneField | Sí | - |
| **tarifas_estudio** | ForeignKey | Sí | - |
| **templates_facturas** | ForeignKey | Sí | - |
| **compra** | ForeignKey | Sí | - |
| **preventas** | ForeignKey | Sí | - |
| **venta** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **ordenes_compra** | ForeignKey | Sí | - |
| **recepciones** | ForeignKey | Sí | - |
| **cuentabancaria** | ForeignKey | Sí | - |
| **recibo** | ForeignKey | Sí | - |
| **ordenpago** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **codigo_id** | AutoField | No | - |
| **razon_social** | CharField | No | - |
| **tipo_documento** | CharField | No | - |
| **cuit** | CharField | Sí | - |
| **fecha_nacimiento** | DateField | Sí | - |
| **tipo_entidad** | IntegerField | No | - |
| **domicilio** | CharField | Sí | - |
| **codigo_postal** | CharField | Sí | - |
| **localidad** | CharField | Sí | - |
| **jurisdiccion** | ForeignKey | Sí | Jurisdiccion |
| **contacto** | CharField | Sí | - |
| **telefono** | CharField | Sí | - |
| **correo** | CharField | Sí | - |
| **condicion_iva** | CharField | No | - |
| **tipo_iibb** | CharField | No | - |
| **saldo_inicial** | DecimalField | No | - |
| **saldo** | DecimalField | No | - |
| **limite** | DecimalField | No | - |
| **objetivo_mensual** | DecimalField | No | - |
| **clasificacion** | CharField | Sí | - |
| **observaciones** | TextField | Sí | - |
| **usa_orden_compra** | BooleanField | No | - |
| **cta_pat** | IntegerField | No | - |
| **cta_res** | IntegerField | No | - |
| **empresa** | ForeignKey | Sí | Empresa |
| **codigo_anterior** | CharField | Sí | - |

### Tabla: `ExtensionArmeria`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **cliente** | OneToOneField | No | - |
| **clu** | CharField | No | - |
| **clu_vto** | DateField | Sí | - |
| **es_policia** | BooleanField | No | - |

### Tabla: `ExtensionJosen`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **cliente** | OneToOneField | No | - |
| **coeficiente** | DecimalField | No | - |
| **rubro** | ForeignKey | Sí | RubroJosen |

### Tabla: `TarifaEstudio`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **cliente** | ForeignKey | No | ClienteProveedor |
| **producto** | ForeignKey | No | Producto |
| **cuenta** | ForeignKey | Sí | Cuenta |
| **tarifa_f** | DecimalField | No | - |
| **tarifa_p** | DecimalField | No | - |
| **activo** | BooleanField | No | - |

### Tabla: `TemplateFacturaProveedor`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **proveedor** | ForeignKey | No | ClienteProveedor |
| **nombre_template** | CharField | No | - |
| **coordenadas** | JSONField | No | - |
| **creado** | DateTimeField | No | - |
| **modificado** | DateTimeField | No | - |

### Tabla: `Compra`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **subproductos** | ForeignKey | Sí | - |
| **items** | ForeignKey | Sí | - |
| **alicuotas** | ForeignKey | Sí | - |
| **retpercs** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **recepciones_generadas** | ForeignKey | Sí | - |
| **pagos_aplicados** | ForeignKey | Sí | - |
| **archivo_pdf** | FileField | Sí | - |
| **compras_id** | AutoField | No | - |
| **asiento_id** | IntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **periodo** | CharField | Sí | - |
| **tipo** | ForeignKey | Sí | TipoComprobante |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **proveedor** | ForeignKey | No | ClienteProveedor |
| **moneda** | CharField | No | - |
| **cotizacion** | DecimalField | No | - |
| **condic** | IntegerField | No | - |
| **descripcion** | CharField | Sí | - |
| **cta_imputacion** | IntegerField | Sí | - |
| **subtotal** | DecimalField | No | - |
| **descuento** | DecimalField | No | - |
| **neto** | DecimalField | No | - |
| **iva** | DecimalField | No | - |
| **no_gravado** | DecimalField | No | - |
| **exento** | DecimalField | No | - |
| **p_iva** | DecimalField | No | - |
| **p_gcia** | DecimalField | No | - |
| **p_iibb** | DecimalField | No | - |
| **p_recbc** | DecimalField | No | - |
| **p_sircreb** | DecimalField | No | - |
| **p_mun** | DecimalField | No | - |
| **otros** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **pagado** | DecimalField | No | - |
| **saldo** | DecimalField | No | - |
| **usuario** | ForeignKey | No | User |
| **modificado** | DateTimeField | No | - |
| **id_fac_rem** | IntegerField | Sí | - |
| **gestion_stock_por_recepcion** | BooleanField | No | - |
| **sucursal** | ForeignKey | No | Sucursal |
| **empresa** | ForeignKey | No | Empresa |
| **ejercicio** | ForeignKey | Sí | Ejercicio |

### Tabla: `CompraItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **imputaciones_oc** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **compra** | ForeignKey | No | Compra |
| **producto** | ForeignKey | No | Producto |
| **cantidad** | DecimalField | No | - |
| **precio_unitario** | DecimalField | No | - |
| **iva_alicuota** | DecimalField | No | - |
| **total** | DecimalField | No | - |

### Tabla: `CompraAlicuota`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **compra** | ForeignKey | No | Compra |
| **codigo** | CharField | No | - |
| **porcentaje** | DecimalField | No | - |
| **neto** | DecimalField | No | - |
| **iva** | DecimalField | No | - |

### Tabla: `CompraRetPerc`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **compra** | ForeignKey | No | Compra |
| **impuesto** | CharField | No | - |
| **tipo** | CharField | No | - |
| **jurisdiccion** | ForeignKey | Sí | Jurisdiccion |
| **importe** | DecimalField | No | - |

### Tabla: `Preventa`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **items** | ForeignKey | Sí | - |
| **preventa_id** | AutoField | No | - |
| **fecha** | DateField | No | - |
| **cliente** | ForeignKey | No | ClienteProveedor |
| **cliente_razon_social** | CharField | Sí | - |
| **cliente_cuit** | CharField | Sí | - |
| **cliente_domicilio** | CharField | Sí | - |
| **vendedor** | ForeignKey | No | User |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **estado** | IntegerField | No | - |
| **neto** | DecimalField | No | - |
| **descuento_global** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **modificado** | DateTimeField | No | - |

### Tabla: `PreventaItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **preventa** | ForeignKey | No | Preventa |
| **producto** | ForeignKey | No | Producto |
| **cantidad** | DecimalField | No | - |
| **precio_unitario** | DecimalField | No | - |
| **porcentaje_descuento** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **moneda_origen** | CharField | No | - |
| **cotizacion_aplicada** | DecimalField | No | - |
| **precio_origen** | DecimalField | No | - |

### Tabla: `Venta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **subproductos** | ForeignKey | Sí | - |
| **items** | ForeignKey | Sí | - |
| **alicuotas_iva** | ForeignKey | Sí | - |
| **movimiento** | ForeignKey | Sí | - |
| **cobros_aplicados** | ForeignKey | Sí | - |
| **movimientocaja** | ForeignKey | Sí | - |
| **ventas_id** | AutoField | No | - |
| **asiento_id** | IntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **fec_vta** | DateTimeField | No | - |
| **periodo** | CharField | Sí | - |
| **periodo_facturado** | CharField | Sí | - |
| **tipo** | ForeignKey | Sí | TipoComprobante |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **cliente** | ForeignKey | No | ClienteProveedor |
| **cliente_razon_social** | CharField | Sí | - |
| **cliente_cuit** | CharField | Sí | - |
| **cliente_domicilio** | CharField | Sí | - |
| **moneda** | CharField | No | - |
| **cotizacion** | DecimalField | No | - |
| **condic** | IntegerField | No | - |
| **neto** | DecimalField | No | - |
| **iva** | DecimalField | No | - |
| **no_gravado** | DecimalField | No | - |
| **exento** | DecimalField | No | - |
| **p_iva** | DecimalField | No | - |
| **p_gcia** | DecimalField | No | - |
| **p_iibb** | DecimalField | No | - |
| **p_recbc** | DecimalField | No | - |
| **p_sircreb** | DecimalField | No | - |
| **p_mun** | DecimalField | No | - |
| **otros** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **cobrado** | DecimalField | No | - |
| **saldo** | DecimalField | No | - |
| **efectivo** | DecimalField | No | - |
| **tarjeta** | DecimalField | No | - |
| **transferencia** | DecimalField | No | - |
| **valores** | DecimalField | No | - |
| **dolares** | DecimalField | No | - |
| **fec_cob** | DateTimeField | Sí | - |
| **estado** | IntegerField | No | - |
| **usuario** | ForeignKey | No | User |
| **vendedor** | ForeignKey | Sí | User |
| **cajero** | ForeignKey | Sí | User |
| **sucursal** | ForeignKey | No | Sucursal |
| **empresa** | ForeignKey | No | Empresa |
| **ejercicio** | ForeignKey | Sí | Ejercicio |
| **cae** | CharField | Sí | - |
| **vto_cae** | DateField | Sí | - |
| **cod_qr** | TextField | Sí | - |
| **id_fac_rem** | IntegerField | Sí | - |

### Tabla: `VentaItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **venta** | ForeignKey | No | Venta |
| **producto** | ForeignKey | No | Producto |
| **concepto** | CharField | Sí | - |
| **cantidad** | DecimalField | No | - |
| **precio_unitario** | DecimalField | No | - |
| **porcentaje_descuento** | DecimalField | No | - |
| **iva_alicuota** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **moneda_origen** | CharField | No | - |
| **cotizacion_aplicada** | DecimalField | No | - |
| **precio_origen** | DecimalField | No | - |
| **credencial** | CharField | Sí | - |
| **dmp** | DecimalField | No | - |

### Tabla: `VentaAlicuotaIva`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **venta** | ForeignKey | No | Venta |
| **id_iva** | IntegerField | No | - |
| **alicuota** | DecimalField | No | - |
| **base_imponible** | DecimalField | No | - |
| **importe_iva** | DecimalField | No | - |

### Tabla: `Movimiento`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **movimiento_id** | AutoField | No | - |
| **asiento_id** | IntegerField | Sí | - |
| **compra** | ForeignKey | Sí | Compra |
| **venta** | ForeignKey | Sí | Venta |
| **producto** | ForeignKey | No | Producto |
| **fecha** | DateField | No | - |
| **tipo** | IntegerField | No | - |
| **punto** | IntegerField | No | - |
| **numero** | IntegerField | No | - |
| **cli_pro** | ForeignKey | No | ClienteProveedor |
| **tipo_mov** | CharField | No | - |
| **entrada** | DecimalField | No | - |
| **salida** | DecimalField | No | - |
| **saldo** | DecimalField | No | - |
| **precio** | DecimalField | No | - |
| **neto** | DecimalField | No | - |
| **stock** | DecimalField | No | - |
| **modificado** | DateTimeField | No | - |
| **ejercicio** | ForeignKey | Sí | Ejercicio |
| **usuario** | ForeignKey | No | User |
| **sucursal** | ForeignKey | No | Sucursal |
| **empresa** | ForeignKey | No | Empresa |

### Tabla: `OrdenCompra`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **items** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **oc_id** | AutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **proveedor** | ForeignKey | No | ClienteProveedor |
| **carga_costos** | BooleanField | No | - |
| **medio_pago** | ForeignKey | Sí | MedioPago |
| **condiciones_pago** | TextField | Sí | - |
| **moneda** | CharField | No | - |
| **cotizacion** | DecimalField | No | - |
| **observaciones** | TextField | Sí | - |
| **estado** | IntegerField | No | - |
| **estado_recepcion** | IntegerField | No | - |
| **estado_facturacion** | IntegerField | No | - |
| **total** | DecimalField | No | - |
| **usuario** | ForeignKey | No | User |

### Tabla: `OrdenCompraItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **imputaciones_recepcion** | ForeignKey | Sí | - |
| **imputaciones_factura** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **orden** | ForeignKey | No | OrdenCompra |
| **producto** | ForeignKey | No | Producto |
| **cod_prov** | CharField | No | - |
| **cantidad** | DecimalField | No | - |
| **cantidad_original** | DecimalField | No | - |
| **precio_unitario** | DecimalField | No | - |
| **iva_alicuota** | DecimalField | No | - |
| **cantidad_recibida** | DecimalField | No | - |
| **cantidad_facturada** | DecimalField | No | - |
| **marcado_diferencia** | BooleanField | No | - |

### Tabla: `Recepcion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **items** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **recepcion_id** | AutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **origen** | CharField | No | - |
| **proveedor** | ForeignKey | Sí | ClienteProveedor |
| **remito_proveedor** | CharField | Sí | - |
| **generada_por_factura** | ForeignKey | Sí | Compra |
| **observaciones** | TextField | Sí | - |
| **estado** | IntegerField | No | - |
| **usuario** | ForeignKey | No | User |

### Tabla: `RecepcionItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **imputaciones** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **recepcion** | ForeignKey | No | Recepcion |
| **producto** | ForeignKey | No | Producto |
| **cantidad_recibida** | DecimalField | No | - |

### Tabla: `RecepcionImputacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **recepcion_item** | ForeignKey | No | RecepcionItem |
| **orden_item** | ForeignKey | Sí | OrdenCompraItem |
| **remito_interno_item** | ForeignKey | Sí | RemitoInternoItem |
| **cantidad** | DecimalField | No | - |

### Tabla: `RemitoInterno`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **items** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **ri_id** | AutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal_origen** | ForeignKey | No | Sucursal |
| **sucursal_destino** | ForeignKey | No | Sucursal |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **tipo** | CharField | No | - |
| **estado** | IntegerField | No | - |
| **observaciones** | TextField | Sí | - |
| **usuario** | ForeignKey | No | User |

### Tabla: `RemitoInternoItem`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **imputaciones_recepcion** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **remito** | ForeignKey | No | RemitoInterno |
| **producto** | ForeignKey | No | Producto |
| **cantidad_enviada** | DecimalField | No | - |
| **cantidad_recibida** | DecimalField | No | - |

### Tabla: `CompraOCImputacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **compra_item** | ForeignKey | No | CompraItem |
| **orden_item** | ForeignKey | No | OrdenCompraItem |
| **cantidad** | DecimalField | No | - |

## Módulo: `TESORERIA`

### Tabla: `Banco`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **valorterceros** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **codigo_bcra** | CharField | Sí | - |
| **nombre** | CharField | No | - |

### Tabla: `Tarjeta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **cobrotarjeta** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **codigo** | CharField | No | - |
| **nombre** | CharField | No | - |
| **tipo** | CharField | No | - |

### Tabla: `MedioPago`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **ordenes_compra** | ForeignKey | Sí | - |
| **movimientocajadetalle** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **codigo** | CharField | No | - |
| **nombre** | CharField | No | - |
| **categoria** | CharField | No | - |
| **cuenta_contable** | ForeignKey | Sí | Cuenta |
| **activo** | BooleanField | No | - |

### Tabla: `CuentaBancaria`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **transaccionbancaria** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **cta_bc_id** | AutoField | No | - |
| **banco** | CharField | No | - |
| **moneda** | CharField | No | - |
| **cta_numero** | CharField | No | - |
| **cbu** | CharField | Sí | - |
| **cli_pro** | ForeignKey | Sí | ClienteProveedor |
| **cuenta_contable** | ForeignKey | Sí | Cuenta |
| **cuenta_contable_cheques** | ForeignKey | Sí | Cuenta |
| **banco_id** | IntegerField | Sí | - |
| **empresa** | ForeignKey | No | Empresa |

### Tabla: `Recibo`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **imputaciones_simples** | ForeignKey | Sí | - |
| **aplicaciones** | ForeignKey | Sí | - |
| **movimientocaja** | ForeignKey | Sí | - |
| **valores_recibidos** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **ejercicio** | ForeignKey | No | Ejercicio |
| **sesion_caja** | ForeignKey | Sí | CajaSesion |
| **tipo** | CharField | No | - |
| **cliente** | ForeignKey | No | ClienteProveedor |
| **fecha** | DateField | No | - |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **moneda** | CharField | No | - |
| **cotizacion** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **observaciones** | TextField | Sí | - |
| **anulado** | BooleanField | No | - |
| **condic** | IntegerField | No | - |
| **asiento_id** | IntegerField | Sí | - |

### Tabla: `ReciboImputacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **recibo** | ForeignKey | No | Recibo |
| **cuenta_contable** | ForeignKey | No | Cuenta |
| **importe** | DecimalField | No | - |
| **leyenda** | CharField | Sí | - |

### Tabla: `ReciboAplicacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **recibo** | ForeignKey | No | Recibo |
| **venta** | ForeignKey | No | Venta |
| **importe** | DecimalField | No | - |
| **importe_pesos** | DecimalField | No | - |

### Tabla: `OrdenPago`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **retenciones_practicadas** | ForeignKey | Sí | - |
| **imputaciones_simples** | ForeignKey | Sí | - |
| **aplicaciones** | ForeignKey | Sí | - |
| **movimientocaja** | ForeignKey | Sí | - |
| **valores_entregados** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **ejercicio** | ForeignKey | No | Ejercicio |
| **sesion_caja** | ForeignKey | Sí | CajaSesion |
| **tipo** | CharField | No | - |
| **proveedor** | ForeignKey | No | ClienteProveedor |
| **fecha** | DateField | No | - |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **total** | DecimalField | No | - |
| **observaciones** | TextField | Sí | - |
| **anulado** | BooleanField | No | - |
| **condic** | IntegerField | No | - |
| **asiento_id** | IntegerField | Sí | - |

### Tabla: `OrdenPagoImputacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **orden_pago** | ForeignKey | No | OrdenPago |
| **cuenta_contable** | ForeignKey | No | Cuenta |
| **importe** | DecimalField | No | - |
| **leyenda** | CharField | Sí | - |

### Tabla: `OrdenPagoAplicacion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **orden_pago** | ForeignKey | No | OrdenPago |
| **compra** | ForeignKey | No | Compra |
| **importe** | DecimalField | No | - |
| **importe_pesos** | DecimalField | No | - |

### Tabla: `Caja`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **sesiones** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **sucursal** | ForeignKey | No | Sucursal |
| **nombre** | CharField | No | - |
| **tipo** | CharField | No | - |
| **activa** | BooleanField | No | - |

### Tabla: `CajaSesion`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **asientos** | ForeignKey | Sí | - |
| **recibo** | ForeignKey | Sí | - |
| **ordenpago** | ForeignKey | Sí | - |
| **movimientos** | ForeignKey | Sí | - |
| **retiros** | ForeignKey | Sí | - |
| **rendiciones_recibidas** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **caja** | ForeignKey | No | Caja |
| **usuario** | ForeignKey | No | User |
| **fecha_apertura** | DateTimeField | No | - |
| **fecha_cierre** | DateTimeField | Sí | - |
| **saldo_inicial** | DecimalField | No | - |
| **saldo_final_calculado** | DecimalField | No | - |
| **saldo_final_declarado** | DecimalField | No | - |
| **estado** | CharField | No | - |
| **numero** | IntegerField | Sí | - |
| **fecha_operativa** | DateField | Sí | - |
| **si_efectivo** | DecimalField | No | - |
| **si_dolares** | DecimalField | No | - |
| **si_valores** | DecimalField | No | - |
| **sf_efectivo** | DecimalField | No | - |
| **sf_dolares** | DecimalField | No | - |
| **sf_valores** | DecimalField | No | - |

### Tabla: `MovimientoCaja`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **detalles** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **sesion** | ForeignKey | No | CajaSesion |
| **fecha** | DateTimeField | No | - |
| **tipo** | CharField | No | - |
| **importe** | DecimalField | No | - |
| **concepto** | CharField | No | - |
| **condic** | IntegerField | No | - |
| **recibo** | ForeignKey | Sí | Recibo |
| **orden_pago** | ForeignKey | Sí | OrdenPago |
| **venta** | ForeignKey | Sí | Venta |

### Tabla: `MovimientoCajaDetalle`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **cobros_tarjeta** | ForeignKey | Sí | - |
| **transacciones_bancarias** | ForeignKey | Sí | - |
| **valores** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **movimiento_caja** | ForeignKey | No | MovimientoCaja |
| **medio_pago** | ForeignKey | No | MedioPago |
| **importe** | DecimalField | No | - |
| **importe_moneda_extranjera** | DecimalField | No | - |
| **cotizacion** | DecimalField | No | - |

### Tabla: `CobroTarjeta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **retirocajatarjeta** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **movimiento_detalle** | ForeignKey | Sí | MovimientoCajaDetalle |
| **tarjeta** | ForeignKey | No | Tarjeta |
| **lote** | CharField | Sí | - |
| **cupon** | CharField | Sí | - |
| **cuotas** | IntegerField | No | - |
| **sucursal_id** | IntegerField | Sí | - |

### Tabla: `TransaccionBancaria`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | Sí | Empresa |
| **tipo_transaccion** | CharField | No | - |
| **movimiento_detalle** | ForeignKey | Sí | MovimientoCajaDetalle |
| **cuenta_bancaria** | ForeignKey | No | CuentaBancaria |
| **numero_operacion** | CharField | Sí | - |
| **importe** | DecimalField | No | - |
| **cuit_contraparte** | CharField | No | - |
| **fecha_operacion** | DateField | No | - |
| **fecha_vencimiento** | DateField | Sí | - |
| **estado** | CharField | No | - |
| **fecha_debito** | DateField | Sí | - |
| **asiento_id** | IntegerField | Sí | - |
| **asiento_debito_id** | IntegerField | Sí | - |

### Tabla: `ValorTerceros`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **retirocajavalor** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | Sí | Empresa |
| **banco** | ForeignKey | No | Banco |
| **numero_cheque** | CharField | No | - |
| **importe** | DecimalField | No | - |
| **fecha_emision** | DateField | No | - |
| **fecha_vencimiento** | DateField | No | - |
| **cuit_firmante** | CharField | No | - |
| **nombre_firmante** | CharField | No | - |
| **sucursal_id** | IntegerField | Sí | - |
| **recibo** | ForeignKey | Sí | Recibo |
| **movimiento_detalle** | ForeignKey | Sí | MovimientoCajaDetalle |
| **fecha_recepcion** | DateField | Sí | - |
| **asiento_recepcion_id** | IntegerField | Sí | - |
| **orden_pago** | ForeignKey | Sí | OrdenPago |
| **fecha_entrega** | DateField | Sí | - |
| **asiento_entrega_id** | IntegerField | Sí | - |
| **estado** | CharField | No | - |

### Tabla: `RetiroCaja`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **retirocajavalor** | ForeignKey | Sí | - |
| **cupones** | ForeignKey | Sí | - |
| **asientos** | ForeignKey | Sí | - |
| **id** | BigAutoField | No | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **sesion** | ForeignKey | No | CajaSesion |
| **tipo** | CharField | No | - |
| **fecha** | DateTimeField | No | - |
| **usuario** | ForeignKey | No | User |
| **sucursal_origen** | ForeignKey | No | Sucursal |
| **sucursal_destino** | ForeignKey | No | Sucursal |
| **efectivo_pesos** | DecimalField | No | - |
| **efectivo_dolares** | DecimalField | No | - |
| **cotizacion_dolar** | DecimalField | No | - |
| **observaciones** | TextField | Sí | - |
| **anulado** | BooleanField | No | - |
| **estado** | CharField | No | - |
| **sesion_recepcion** | ForeignKey | Sí | CajaSesion |
| **usuario_recepcion** | ForeignKey | Sí | User |
| **fecha_recepcion** | DateTimeField | Sí | - |
| **efectivo_pesos_recibido** | DecimalField | No | - |
| **efectivo_dolares_recibido** | DecimalField | No | - |
| **diferencia_pesos** | DecimalField | No | - |
| **asiento_diferencia_id** | IntegerField | Sí | - |

### Tabla: `RetiroCajaValor`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **retiro** | ForeignKey | No | RetiroCaja |
| **valor** | ForeignKey | No | ValorTerceros |

### Tabla: `RetiroCajaTarjeta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **retiro** | ForeignKey | No | RetiroCaja |
| **cobro_tarjeta** | ForeignKey | No | CobroTarjeta |

### Tabla: `RetiroCajaAsiento`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **retiro** | ForeignKey | No | RetiroCaja |
| **asiento_id** | IntegerField | No | - |

## Módulo: `CONTABLE`

### Tabla: `Cuenta`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **subcuentas** | ForeignKey | Sí | - |
| **asientolinea** | ForeignKey | Sí | - |
| **rubros_ventas** | ForeignKey | Sí | - |
| **rubros_compras** | ForeignKey | Sí | - |
| **tarifaestudio** | ForeignKey | Sí | - |
| **mediopago** | ForeignKey | Sí | - |
| **cuentabancaria** | ForeignKey | Sí | - |
| **cuentas_bancarias_cheques** | ForeignKey | Sí | - |
| **reciboimputacion** | ForeignKey | Sí | - |
| **ordenpagoimputacion** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **id** | AutoField | No | - |
| **codigo** | IntegerField | Sí | - |
| **sumariza** | ForeignKey | Sí | Cuenta |
| **jerarquia** | CharField | No | - |
| **cuenta** | CharField | No | - |
| **imputable** | IntegerField | No | - |
| **tipo** | CharField | No | - |
| **rg_830** | IntegerField | Sí | - |
| **id_pre** | IntegerField | Sí | - |
| **id_bce** | IntegerField | Sí | - |
| **id_ec** | IntegerField | Sí | - |
| **id_fc** | IntegerField | Sí | - |
| **tipo_disponibilidad** | CharField | No | - |
| **empresa** | ForeignKey | No | Empresa |

### Tabla: `Asiento`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **lineas** | ForeignKey | Sí | - |
| **creado_por** | ForeignKey | Sí | User |
| **modificado_por** | ForeignKey | Sí | User |
| **fecha_creacion** | DateTimeField | No | - |
| **fecha_modificacion** | DateTimeField | No | - |
| **asiento_id** | AutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **ejercicio** | ForeignKey | No | Ejercicio |
| **sucursal** | ForeignKey | Sí | Sucursal |
| **numero_diario** | IntegerField | Sí | - |
| **fecha** | DateField | No | - |
| **concepto** | CharField | No | - |
| **condic** | IntegerField | No | - |
| **monto** | DecimalField | No | - |
| **modulo** | IntegerField | No | - |
| **cli_pro** | ForeignKey | Sí | ClienteProveedor |
| **fec_vto** | DateField | Sí | - |
| **anulado** | BooleanField | No | - |
| **fec_anulacion** | DateTimeField | Sí | - |
| **sesion_caja** | ForeignKey | Sí | CajaSesion |

### Tabla: `AsientoLinea`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **asiento** | ForeignKey | No | Asiento |
| **orden** | IntegerField | No | - |
| **cuenta** | ForeignKey | No | Cuenta |
| **leyenda** | CharField | No | - |
| **debe** | DecimalField | No | - |
| **haber** | DecimalField | No | - |
| **divisa** | CharField | No | - |
| **cotizacion** | DecimalField | No | - |
| **debe_divisa** | DecimalField | No | - |
| **haber_divisa** | DecimalField | No | - |
| **fec_vto** | DateField | Sí | - |
| **cli_pro** | ForeignKey | Sí | ClienteProveedor |

### Tabla: `ParametrosContables`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **empresa** | OneToOneField | No | - |
| **cta_iva_credito** | ForeignKey | Sí | Cuenta |
| **cta_iva_debito** | ForeignKey | Sí | Cuenta |
| **cta_ret_iva** | ForeignKey | Sí | Cuenta |
| **cta_ret_ganancias** | ForeignKey | Sí | Cuenta |
| **cta_ret_iibb** | ForeignKey | Sí | Cuenta |
| **cta_ret_suss** | ForeignKey | Sí | Cuenta |
| **cta_ret_mun** | ForeignKey | Sí | Cuenta |
| **cta_ret_practicada_ganancias** | ForeignKey | Sí | Cuenta |
| **cta_ret_practicada_iva** | ForeignKey | Sí | Cuenta |
| **cta_ret_practicada_iibb** | ForeignKey | Sí | Cuenta |
| **cta_ret_practicada_suss** | ForeignKey | Sí | Cuenta |
| **cta_caja** | ForeignKey | Sí | Cuenta |
| **cta_dolar** | ForeignKey | Sí | Cuenta |
| **cta_caja_mostrador** | ForeignKey | Sí | Cuenta |
| **cta_caja_mostrador_dolares** | ForeignKey | Sí | Cuenta |
| **cta_caja_central** | ForeignKey | Sí | Cuenta |
| **cta_caja_central_dolares** | ForeignKey | Sí | Cuenta |
| **cta_transferencias_sucursal** | ForeignKey | Sí | Cuenta |
| **cta_valores_cartera** | ForeignKey | Sí | Cuenta |
| **cta_tarjetas_a_cobrar** | ForeignKey | Sí | Cuenta |
| **cta_diferencia_caja** | ForeignKey | Sí | Cuenta |
| **cta_ventas** | ForeignKey | Sí | Cuenta |
| **cta_compras** | ForeignKey | Sí | Cuenta |
| **cta_clientes_default** | ForeignKey | Sí | Cuenta |
| **cta_proveedores_default** | ForeignKey | Sí | Cuenta |
| **cta_impuestos_internos** | ForeignKey | Sí | Cuenta |
| **cta_itc** | ForeignKey | Sí | Cuenta |
| **cta_bonificaciones** | ForeignKey | Sí | Cuenta |
| **cta_descuentos_obtenidos** | ForeignKey | Sí | Cuenta |
| **cta_resultado_ejercicio** | ForeignKey | Sí | Cuenta |
| **metodo_contabilizacion_ventas** | IntegerField | No | - |

### Tabla: `LibroIvaCompras`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **asiento_id** | IntegerField | No | - |
| **fecha** | DateField | No | - |
| **clienteproveedor** | ForeignKey | No | ClienteProveedor |
| **codiva** | CharField | No | - |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **cuit** | CharField | No | - |
| **neto_gravado** | DecimalField | No | - |
| **exento** | DecimalField | No | - |
| **no_gravado** | DecimalField | No | - |
| **iva_total** | DecimalField | No | - |
| **otros** | DecimalField | No | - |
| **total** | DecimalField | No | - |

### Tabla: `LibroIvaVentas`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **asiento_id** | IntegerField | No | - |
| **fecha** | DateField | No | - |
| **clienteproveedor** | ForeignKey | No | ClienteProveedor |
| **codiva** | CharField | No | - |
| **punto** | IntegerField | No | - |
| **numero** | BigIntegerField | No | - |
| **cuit** | CharField | No | - |
| **neto_gravado** | DecimalField | No | - |
| **exento** | DecimalField | No | - |
| **no_gravado** | DecimalField | No | - |
| **iva_total** | DecimalField | No | - |
| **otros** | DecimalField | No | - |
| **total** | DecimalField | No | - |
| **cae** | CharField | No | - |
| **vto_cae** | DateField | Sí | - |
| **codigo_qr** | TextField | No | - |

### Tabla: `LibroIvaAlic`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **asiento_id** | IntegerField | No | - |
| **c_v** | CharField | No | - |
| **neto** | DecimalField | No | - |
| **alicuota** | DecimalField | No | - |
| **iva** | DecimalField | No | - |
| **computable** | DecimalField | No | - |
| **codiva** | CharField | No | - |

### Tabla: `RetPercSufrida`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **asiento_id** | IntegerField | No | - |
| **origen** | CharField | No | - |
| **tipo** | CharField | No | - |
| **impuesto** | CharField | No | - |
| **base** | DecimalField | No | - |
| **alicuota** | DecimalField | No | - |
| **importe** | DecimalField | No | - |
| **jurisdiccion** | ForeignKey | Sí | Jurisdiccion |
| **nro_certificado** | CharField | No | - |
| **fecha** | DateField | Sí | - |
| **cuit_agente** | CharField | No | - |
| **razon_social_agente** | CharField | No | - |
| **regimen** | CharField | No | - |

### Tabla: `RetencionPracticada`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **empresa** | ForeignKey | No | Empresa |
| **orden_pago** | ForeignKey | No | OrdenPago |
| **proveedor** | ForeignKey | No | ClienteProveedor |
| **impuesto** | CharField | No | - |
| **regimen** | CharField | No | - |
| **nro_certificado** | CharField | No | - |
| **fecha** | DateField | No | - |
| **base** | DecimalField | No | - |
| **alicuota** | DecimalField | No | - |
| **importe** | DecimalField | No | - |
| **cuit_retenido** | CharField | No | - |
| **asiento_id** | IntegerField | Sí | - |

### Tabla: `AlicuotaIva`

| Campo | Tipo de Dato | ¿Permite Nulo? | Clave Foránea a |
|---|---|---|---|
| **id** | BigAutoField | No | - |
| **codigo** | CharField | No | - |
| **descripcion** | CharField | No | - |
| **porcentaje** | DecimalField | No | - |
| **activo** | BooleanField | No | - |
| **orden** | IntegerField | No | - |

