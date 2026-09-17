"""
Servicio de persistencia transaccional atómica para Liquidaciones Primarias de Granos (LPG).

Crea de forma sincronizada y consistente:
1. Comprador en ClienteProveedor (si no existía o actualización de cta_pat).
2. Nuevas reglas de GastoMapeo (auto-aprendizaje de gastos).
3. Venta (facturacion_venta), Ítems (facturacion_ventaitem) y Alícuotas (facturacion_ventaalicuota).
4. Compra de Gastos/Deducciones (facturacion_compra) y Alícuotas (facturacion_compraalicuota).
5. Asiento Contable Unificado (cble_asiento_enc) y Líneas (cble_asiento_mov) contra cta_pat.
6. Libro IVA Ventas (cble_libro_iva_ventas) y Alícuotas (cble_libro_iva_alic c_v='V').
7. Libro IVA Compras (cble_libro_iva_compras) y Alícuotas (cble_libro_iva_alic c_v='C').
8. Retenciones Sufridas (cble_ret_perc_sufrida).
"""
import contextlib
from decimal import Decimal
from django.db import transaction
from django.db.models.signals import post_save
from facturacion.models import (
    ClienteProveedor,
    TipoComprobante,
    Venta,
    VentaItem,
    VentaAlicuotaIva,
    Compra,
    CompraAlicuota
)
from facturacion.signals import (
    actualizar_saldo_cliente_post_save,
    actualizar_saldo_proveedor_post_save
)
from contable.services.saldos import recalcular_saldo_cliente_proveedor
from contable.models import (
    Asiento,
    AsientoLinea,
    LibroIvaVentas,
    LibroIvaCompras,
    LibroIvaAlic,
    RetPercSufrida,
    ParametrosContables,
    Cuenta
)
from empresas.models import Ejercicio, Sucursal
from verticalidades.agricola.granos.models import GranoMapeo, GastoMapeo


@contextlib.contextmanager
def pausar_senales_contables():
    """
    Desconecta temporalmente las señales de auto-contabilización de Venta y Compra
    para evitar que pisen el asiento unificado o fallen por falta de cuentas comerciales.
    """
    post_save.disconnect(actualizar_saldo_cliente_post_save, sender=Venta)
    post_save.disconnect(actualizar_saldo_proveedor_post_save, sender=Compra)
    try:
        yield
    finally:
        post_save.connect(actualizar_saldo_cliente_post_save, sender=Venta)
        post_save.connect(actualizar_saldo_proveedor_post_save, sender=Compra)


class LpgPersister:
    """
    Motor de persistencia transaccional para liquidaciones de granos.
    """

    @classmethod
    def persistir_liquidacion(cls, empresa, sucursal, usuario, matched_data, overrides=None):
        with pausar_senales_contables():
            return cls._persistir_liquidacion_inner(empresa, sucursal, usuario, matched_data, overrides)

    @classmethod
    @transaction.atomic
    def _persistir_liquidacion_inner(cls, empresa, sucursal, usuario, matched_data, overrides=None):
        """
        Guarda la liquidación en la base de datos de manera 100% transaccional.
        
        `overrides` permite sobreescribir valores desde el formulario de previsualización:
        - `cta_pat_cliente_id`: ID de cuenta patrimonial si el cliente no la tenía.
        - `grano_producto_id`: ID del producto si no estaba mapeado.
        - `grano_cta_ventas_id`: ID de cuenta ventas si no estaba mapeada.
        - `nuevos_gastos_mapeo`: Lista de dicts [{'patron': '...', 'descripcion': '...', 'cta_gasto_id': 123}]
        """
        overrides = overrides or {}
        parsed = matched_data['parsed']

        # 1. Obtener parámetros contables y ejercicio
        params_contables = ParametrosContables.objects.filter(empresa=empresa).first()
        if not params_contables:
            raise ValueError(f"No se encontraron Parámetros Contables configurados para la empresa {empresa.nombre}.")

        fecha_lpg = parsed['fecha']
        ejercicio = Ejercicio.objects.filter(
            empresa=empresa,
            inicio__lte=fecha_lpg,
            cierre__gte=fecha_lpg
        ).first()
        if not ejercicio:
            ejercicio = Ejercicio.objects.filter(empresa=empresa).order_by('-inicio').first()

        # 2. Resolver o Crear Cliente/Comprador
        comp_info = parsed.get('comprador', {})
        cuit_comp = comp_info.get('cuit', '').strip()
        cliente = ClienteProveedor.objects.filter(empresa=empresa, cuit=cuit_comp).first()
        
        cta_pat_id = overrides.get('cta_pat_cliente_id') or (matched_data.get('comprador_match') or {}).get('cta_pat')

        if not cliente:
            # Crear Cliente con datos del PDF
            cliente = ClienteProveedor(
                empresa=empresa,
                cuit=cuit_comp,
                razon_social=comp_info.get('razon_social', 'COMPRADOR GRANOS').upper(),
                domicilio=comp_info.get('domicilio', ''),
                localidad=comp_info.get('localidad', ''),
                condicion_iva=comp_info.get('condicion_iva') or 'RESPONSABLE INSCRIPTO',
                tipo_entidad=1,  # Cliente
                tipo_documento='80',  # CUIT
                cta_pat=cta_pat_id or 0
            )
            cliente.save()
        else:
            if cta_pat_id and cliente.cta_pat != cta_pat_id:
                cliente.cta_pat = cta_pat_id
                cliente.save(update_fields=['cta_pat'])

        # Obtener objeto Cuenta para la cta_pat del cliente
        cuenta_pat_obj = None
        if cliente.cta_pat:
            cuenta_pat_obj = Cuenta.objects.filter(empresa=empresa, id=cliente.cta_pat).first()
            if not cuenta_pat_obj:
                cuenta_pat_obj = Cuenta.objects.filter(empresa=empresa, codigo=cliente.cta_pat).first()
        
        if not cuenta_pat_obj and params_contables.cta_clientes_default:
            cuenta_pat_obj = params_contables.cta_clientes_default

        if not cuenta_pat_obj:
            raise ValueError(f"No se pudo determinar la Cuenta Contable Patrimonial para el cliente {cliente.razon_social}.")

        # 3. Guardar nuevas reglas de GastoMapeo si fueron provistas en el preview (Auto-aprendizaje)
        nuevos_gastos = overrides.get('nuevos_gastos_mapeo', [])
        for ng in nuevos_gastos:
            patron_limpio = ng.get('patron', '').strip().upper()
            cta_gasto_id = ng.get('cta_gasto_id')
            if patron_limpio and cta_gasto_id:
                cta_gasto_obj = Cuenta.objects.get(id=cta_gasto_id)
                GastoMapeo.objects.update_or_create(
                    empresa=empresa,
                    patron=patron_limpio,
                    defaults={
                        'descripcion': ng.get('descripcion') or patron_limpio,
                        'cta_gasto': cta_gasto_obj,
                        'alicuota_sugerida': Decimal(str(ng.get('alicuota_sugerida') or '10.50'))
                    }
                )

        # 4. Resolver Grano / Cultivo y Cuenta de Ventas
        grano_match = matched_data.get('grano_match') or {}
        producto_id = overrides.get('grano_producto_id') or grano_match.get('producto_id')
        cta_ventas_id = overrides.get('grano_cta_ventas_id') or grano_match.get('cta_ventas_id')

        if not producto_id or not cta_ventas_id:
            raise ValueError("Falta definir el Producto ERP o la Cuenta Contable de Ventas para el grano liquidado.")

        from productos.models import Producto
        producto_obj = Producto.objects.get(id=producto_id)
        cta_ventas_obj = Cuenta.objects.get(id=cta_ventas_id)

        # Si el grano no estaba en GranoMapeo, guardarlo para el futuro
        cod_grano = parsed.get('grano', {}).get('codigo_arca', 0)
        if cod_grano and not grano_match.get('codigo_arca'):
            GranoMapeo.objects.update_or_create(
                empresa=empresa,
                codigo_arca=cod_grano,
                defaults={
                    'descripcion_arca': parsed.get('grano', {}).get('descripcion_arca', ''),
                    'producto': producto_obj,
                    'cta_ventas': cta_ventas_obj
                }
            )

        # 5. Resolver Tipos de Comprobantes
        es_ajuste = parsed.get('es_ajuste', False)
        tipo_ajuste = parsed.get('tipo_ajuste')
        
        if es_ajuste:
            if tipo_ajuste == 'CREDITO':
                tipo_venta, _ = TipoComprobante.objects.get_or_create(
                    codigo='035',
                    defaults={'detalle': 'AJUSTE CREDITO LIQUIDACION GRANOS', 'signo': -1, 'estado': True}
                )
            else:
                tipo_venta, _ = TipoComprobante.objects.get_or_create(
                    codigo='034',
                    defaults={'detalle': 'AJUSTE DEBITO LIQUIDACION GRANOS', 'signo': 1, 'estado': True}
                )
        else:
            tipo_venta, _ = TipoComprobante.objects.get_or_create(
                codigo='033',
                defaults={'detalle': 'LIQUIDACION PRIMARIA DE GRANOS', 'signo': 1, 'estado': True}
            )

        tipo_compra_gasto, _ = TipoComprobante.objects.get_or_create(
            codigo='033',
            defaults={'detalle': 'LIQUIDACION DE GASTOS GRANOS', 'signo': 1, 'estado': True}
        )

        # 6. Calcular Totales y Números
        coe = parsed.get('coe', '').strip()
        punto = int(coe[:4]) if len(coe) >= 8 else 1
        numero = int(coe[4:]) if len(coe) >= 8 else (int(coe) if coe.isdigit() else 1)

        grano_dict = parsed.get('grano', {})
        neto_venta = Decimal(str(grano_dict.get('subtotal') or '0.00'))
        iva_venta = Decimal(str(grano_dict.get('importe_iva') or '0.00'))
        total_venta = Decimal(str(grano_dict.get('total_operacion') or '0.00'))
        if total_venta == Decimal('0.00'):
            total_venta = neto_venta + iva_venta

        kilos = Decimal(str(grano_dict.get('kilos') or '0.00'))
        precio_unitario = Decimal(str(grano_dict.get('precio_unitario') or '0.00'))

        # Totales de Deducciones
        deducciones_list = matched_data.get('deducciones_matched', [])
        neto_deducciones = sum((Decimal(str(d['base_calculo'])) for d in deducciones_list), Decimal('0.00'))
        iva_deducciones = sum((Decimal(str(d['importe_iva'])) for d in deducciones_list), Decimal('0.00'))
        total_deducciones = sum((Decimal(str(d['total'])) for d in deducciones_list), Decimal('0.00'))

        # Totales de Retenciones
        retenciones_list = parsed.get('retenciones', [])
        total_retenciones = sum((Decimal(str(r['importe'])) for r in retenciones_list), Decimal('0.00'))

        # 7. Crear Asiento Contable Unificado (cble_asiento_enc)
        concepto_asiento = f"LPG {parsed.get('tipo_operacion', '')} COE {coe} - {grano_dict.get('descripcion_arca', '')}".strip()
        asiento = Asiento.objects.create(
            empresa=empresa,
            ejercicio=ejercicio,
            sucursal=sucursal,
            fecha=fecha_lpg,
            concepto=concepto_asiento.upper()[:200],
            condic=1,  # Real / Fiscal
            monto=total_venta if total_venta > 0 else total_deducciones,
            modulo=2,  # Ventas
            cli_pro=cliente
        )

        # 8. Generar Líneas del Asiento (cble_asiento_mov)
        orden = 1
        signo_factor = Decimal('-1') if (es_ajuste and tipo_ajuste == 'CREDITO') else Decimal('1')

        # Línea 1: Cliente.cta_pat por el Total Venta (DEBE si venta normal)
        if total_venta > Decimal('0.00'):
            if signo_factor > 0:
                AsientoLinea.objects.create(
                    asiento=asiento, orden=orden, cuenta=cuenta_pat_obj,
                    debe=total_venta, haber=0,
                    leyenda=f"LPG {coe} Total Venta {cliente.razon_social}"[:200], cli_pro=cliente
                )
            else:
                AsientoLinea.objects.create(
                    asiento=asiento, orden=orden, cuenta=cuenta_pat_obj,
                    debe=0, haber=total_venta,
                    leyenda=f"LPG {coe} Ajuste Crédito Venta {cliente.razon_social}"[:200], cli_pro=cliente
                )
            orden += 1

            # Línea 2: Cuenta Ventas Grano por el Neto (HABER si venta normal)
            if signo_factor > 0:
                AsientoLinea.objects.create(
                    asiento=asiento, orden=orden, cuenta=cta_ventas_obj,
                    debe=0, haber=neto_venta,
                    leyenda=f"Venta {grano_dict.get('descripcion_arca', '')} {kilos} Kg @ ${precio_unitario}"[:200],
                    cli_pro=cliente
                )
            else:
                AsientoLinea.objects.create(
                    asiento=asiento, orden=orden, cuenta=cta_ventas_obj,
                    debe=neto_venta, haber=0,
                    leyenda=f"Ajuste Venta {grano_dict.get('descripcion_arca', '')}"[:200],
                    cli_pro=cliente
                )
            orden += 1

            # Línea 3: IVA Débito Fiscal (HABER si venta normal)
            if iva_venta > Decimal('0.00') and params_contables.cta_iva_debito:
                if signo_factor > 0:
                    AsientoLinea.objects.create(
                        asiento=asiento, orden=orden, cuenta=params_contables.cta_iva_debito,
                        debe=0, haber=iva_venta,
                        leyenda=f"IVA Débito Fiscal 10.5% LPG {coe}"[:200], cli_pro=cliente
                    )
                else:
                    AsientoLinea.objects.create(
                        asiento=asiento, orden=orden, cuenta=params_contables.cta_iva_debito,
                        debe=iva_venta, haber=0,
                        leyenda=f"Ajuste IVA Débito Fiscal LPG {coe}"[:200], cli_pro=cliente
                    )
                orden += 1

        # Líneas de Deducciones / Gastos
        if total_deducciones > Decimal('0.00'):
            # Líneas de Gasto individual (DEBE)
            for d in deducciones_list:
                cta_g_id = d.get('cta_gasto_id')
                base_g = Decimal(str(d['base_calculo']))
                if base_g > Decimal('0.00'):
                    if cta_g_id:
                        cta_g_obj = Cuenta.objects.filter(id=cta_g_id).first()
                    else:
                        cta_g_obj = None

                    if not cta_g_obj:
                        cta_g_obj = params_contables.cta_compras or cuenta_pat_obj

                    AsientoLinea.objects.create(
                        asiento=asiento, orden=orden, cuenta=cta_g_obj,
                        debe=base_g, haber=0,
                        leyenda=f"Gasto LPG: {d['concepto_original']}"[:200], cli_pro=cliente
                    )
                    orden += 1

            # IVA Crédito Fiscal de Gastos (DEBE)
            if iva_deducciones > Decimal('0.00') and params_contables.cta_iva_credito:
                AsientoLinea.objects.create(
                    asiento=asiento, orden=orden, cuenta=params_contables.cta_iva_credito,
                    debe=iva_deducciones, haber=0,
                    leyenda=f"IVA Crédito Fiscal Deducciones LPG {coe}"[:200], cli_pro=cliente
                )
                orden += 1

            # Total Deducciones contra la cuenta del cliente (HABER)
            AsientoLinea.objects.create(
                asiento=asiento, orden=orden, cuenta=cuenta_pat_obj,
                debe=0, haber=total_deducciones,
                leyenda=f"Deducciones Comerciales LPG {coe}"[:200], cli_pro=cliente
            )
            orden += 1

        # Líneas de Retenciones Sufridas
        if total_retenciones > Decimal('0.00'):
            for r in retenciones_list:
                imp = Decimal(str(r['importe']))
                if imp > Decimal('0.00'):
                    cta_ret = params_contables.cta_ret_iva if r['impuesto'] == 'IVA' else params_contables.cta_ret_ganancias
                    if not cta_ret:
                        cta_ret = cuenta_pat_obj
                    
                    AsientoLinea.objects.create(
                        asiento=asiento, orden=orden, cuenta=cta_ret,
                        debe=imp, haber=0,
                        leyenda=f"{r['concepto']} LPG {coe}"[:200], cli_pro=cliente
                    )
                    orden += 1

            # Total Retenciones contra la cuenta del cliente (HABER)
            AsientoLinea.objects.create(
                asiento=asiento, orden=orden, cuenta=cuenta_pat_obj,
                debe=0, haber=total_retenciones,
                leyenda=f"Retenciones Sufridas LPG {coe}"[:200], cli_pro=cliente
            )
            orden += 1

        # 9. Crear Comprobante de Venta (facturacion_venta)
        venta = Venta.objects.create(
            asiento_id=asiento.asiento_id,
            fecha=fecha_lpg,
            periodo=parsed.get('periodo') or fecha_lpg.strftime('%Y%m'),
            tipo=tipo_venta,
            punto=punto,
            numero=numero,
            cliente=cliente,
            cliente_razon_social=cliente.razon_social,
            cliente_cuit=cliente.cuit,
            cliente_domicilio=cliente.domicilio_completo,
            moneda='PES',
            cotizacion=Decimal(str(parsed.get('datos_adicionales', {}).get('tipo_cambio') or '1.00')),
            condic=1,
            neto=neto_venta,
            iva=iva_venta,
            total=total_venta,
            cobrado=total_venta,  # Liquidado en cuenta corriente
            saldo=Decimal('0.00'),
            estado=0,
            usuario=usuario,
            sucursal=sucursal,
            empresa=empresa,
            ejercicio=ejercicio,
            cae=coe,
            condicion_venta='CTA_CTE'
        )

        # 10. Crear Ítem de Venta (facturacion_ventaitem)
        VentaItem.objects.create(
            venta=venta,
            producto=producto_obj,
            concepto=f"LIQUIDACION PRIMARIA GRANOS - {grano_dict.get('descripcion_arca', '')} - COE {coe}"[:255],
            cantidad=kilos if kilos > 0 else Decimal('1.00'),
            precio_unitario=precio_unitario if precio_unitario > 0 else neto_venta,
            iva_alicuota=Decimal('10.50'),
            total=neto_venta
        )

        # 11. Crear Alícuota de Venta (facturacion_ventaalicuota)
        if neto_venta > Decimal('0.00') or iva_venta > Decimal('0.00'):
            VentaAlicuotaIva.objects.create(
                venta=venta,
                id_iva=4,  # Código 4 = 10.5% en ARCA
                alicuota=Decimal('10.50'),
                base_imponible=neto_venta,
                importe_iva=iva_venta
            )

        # 12. Crear Libro IVA Ventas y Alícuota
        LibroIvaVentas.objects.create(
            empresa=empresa,
            asiento_id=asiento.asiento_id,
            fecha=fecha_lpg,
            periodo=parsed.get('periodo') or fecha_lpg.strftime('%Y%m'),
            clienteproveedor=cliente,
            codiva=tipo_venta.codigo,
            punto=punto,
            numero=numero,
            cuit=cliente.cuit or '',
            cae=coe,
            neto_gravado=neto_venta,
            iva_total=iva_venta,
            total=total_venta
        )

        if neto_venta > Decimal('0.00') or iva_venta > Decimal('0.00'):
            LibroIvaAlic.objects.create(
                asiento_id=asiento.asiento_id,
                c_v='V',
                neto=neto_venta,
                alicuota=Decimal('10.50'),
                iva=iva_venta,
                computable=iva_venta,
                codiva='0004'  # Código ARCA 10.5%
            )

        # 13. Crear Compra de Gastos/Deducciones (facturacion_compra) si existen
        compra_creada = None
        if total_deducciones > Decimal('0.00'):
            primer_cta_gasto = deducciones_list[0].get('cta_gasto_id') if deducciones_list else None
            
            compra_creada = Compra.objects.create(
                asiento_id=asiento.asiento_id,
                fecha=fecha_lpg,
                periodo=parsed.get('periodo') or fecha_lpg.strftime('%Y%m'),
                tipo=tipo_compra_gasto,
                punto=punto,
                numero=numero,
                proveedor=cliente,
                moneda='PES',
                cotizacion=Decimal('1.00'),
                condic=1,
                descripcion=f"GASTOS Y DEDUCCIONES COMERCIALES LPG COE {coe}"[:255],
                cta_imputacion=primer_cta_gasto,
                subtotal=neto_deducciones,
                neto=neto_deducciones,
                iva=iva_deducciones,
                total=total_deducciones,
                pagado=total_deducciones,
                saldo=Decimal('0.00'),
                usuario=usuario,
                sucursal=sucursal,
                empresa=empresa,
                ejercicio=ejercicio
            )

            # Desglose de Alícuotas de Compra agrupadas por porcentaje
            alicuotas_dict = {}
            for d in deducciones_list:
                alic = Decimal(str(d['alicuota_iva']))
                if alic not in alicuotas_dict:
                    alicuotas_dict[alic] = {'neto': Decimal('0.00'), 'iva': Decimal('0.00')}
                alicuotas_dict[alic]['neto'] += Decimal(str(d['base_calculo']))
                alicuotas_dict[alic]['iva'] += Decimal(str(d['importe_iva']))

            for alic, valores in alicuotas_dict.items():
                cod_arca = '0004' if alic == Decimal('10.50') else ('0005' if alic == Decimal('21.00') else '0003')
                CompraAlicuota.objects.create(
                    compra=compra_creada,
                    codigo=cod_arca,
                    porcentaje=alic,
                    neto=valores['neto'],
                    iva=valores['iva']
                )
                
                # Libro IVA Alícuotas Compras
                LibroIvaAlic.objects.create(
                    asiento_id=asiento.asiento_id,
                    c_v='C',
                    neto=valores['neto'],
                    alicuota=alic,
                    iva=valores['iva'],
                    computable=valores['iva'],
                    codiva=cod_arca
                )

            # Libro IVA Compras
            LibroIvaCompras.objects.create(
                empresa=empresa,
                asiento_id=asiento.asiento_id,
                fecha=fecha_lpg,
                periodo=parsed.get('periodo') or fecha_lpg.strftime('%Y%m'),
                clienteproveedor=cliente,
                codiva=tipo_compra_gasto.codigo,
                punto=punto,
                numero=numero,
                cuit=cliente.cuit or '',
                cae=coe,
                neto_gravado=neto_deducciones,
                iva_total=iva_deducciones,
                total=total_deducciones
            )

        # 14. Registrar Retenciones Sufridas (cble_ret_perc_sufrida)
        for r in retenciones_list:
            imp = Decimal(str(r['importe']))
            if imp > Decimal('0.00'):
                RetPercSufrida.objects.create(
                    empresa=empresa,
                    asiento_id=asiento.asiento_id,
                    origen='V',
                    tipo='R',
                    impuesto=r['impuesto'],
                    base=Decimal(str(r['base_calculo'])),
                    alicuota=Decimal(str(r['alicuota'])),
                    importe=imp,
                    nro_certificado=coe,
                    fecha=fecha_lpg,
                    cuit_agente=cliente.cuit or '',
                    razon_social_agente=cliente.razon_social or '',
                    regimen='RG 4310' if r['impuesto'] == 'IVA' else 'RG 830'
                )

        # 15. Actualizar saldo de cuenta corriente del cliente
        recalcular_saldo_cliente_proveedor(cliente.pk)

        return {
            'asiento_id': asiento.asiento_id,
            'ventas_id': venta.ventas_id,
            'compras_id': compra_creada.compras_id if compra_creada else None,
            'coe': coe,
            'cliente': cliente.razon_social,
            'total_venta': str(total_venta),
            'total_deducciones': str(total_deducciones),
            'total_retenciones': str(total_retenciones),
            'neto_a_pagar': str(parsed.get('totales', {}).get('importe_neto_pagar') or '0.00')
        }
