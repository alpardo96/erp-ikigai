from decimal import Decimal, ROUND_HALF_UP
import calendar
from datetime import date

from core.services.numeracion import siguiente_numero_pre
from django.db import transaction
from django.utils import timezone
from facturacion.models import Venta, VentaItem, VentaAlicuotaIva, ClienteProveedor, TipoComprobante
from verticalidades.estudio.models import TarifaEstudio, EnvioFacturaEstudio
from productos.models import Producto, MovimientoStock, Sucursal
from facturacion.services.afip_service import AFIPService
from facturacion.views import validar_y_obtener_documento_receptor

class FacturacionLoteEstudioService:
    def __init__(self, empresa_id, usuario):
        self.empresa_id = empresa_id
        self.usuario = usuario
        self.resultados = []

    def procesar_lote(self, lote_datos, periodo, pto_vta_id, modo_prueba=False):
        self.resultados = []
        
        tipo_interno = TipoComprobante.objects.filter(codigo='PRE').first()
        if not tipo_interno:
            raise ValueError(
                "Falta configurar el tipo de comprobante 'PRE' (Comprobante Interno). "
                "Cargalo en Configuración → Tipos de Comprobante antes de facturar.")

        from empresas.models import PuntoVenta, Empresa
        pto_vta_obj = PuntoVenta.objects.filter(
            id=pto_vta_id, empresa_id=self.empresa_id).select_related('sucursal').first()
        if not pto_vta_obj:
            raise ValueError(
                "No se pudo resolver el punto de venta indicado para esta empresa. "
                "Verificá la configuración de Puntos de Venta.")
            
        empresa_obj = Empresa.objects.get(pk=self.empresa_id)

        numero_pto = pto_vta_obj.numero
        sucursal_id = pto_vta_obj.sucursal_id
        if not sucursal_id:
            raise ValueError("El punto de venta no tiene sucursal asociada.")

        punto_interno = sucursal_id
        
        # Calcular fechas para el servicio
        # periodo viene como 'YYYYMM'
        if not periodo or len(periodo) != 6:
            raise ValueError("El período debe tener el formato YYYYMM")
            
        try:
            year = int(periodo[:4])
            month = int(periodo[4:])
            fch_serv_desde = date(year, month, 1)
            last_day = calendar.monthrange(year, month)[1]
            fch_serv_hasta = date(year, month, last_day)
        except Exception as e:
            raise ValueError(f"Error calculando fechas del servicio para el período {periodo}: {str(e)}")
            
        fch_vto_pago = timezone.localdate()
        fecha_cbte_str = fch_vto_pago.strftime('%Y%m%d')

        for item in lote_datos:
            id_tarifa = item.get('id_tarifa')
            cliente_id = item.get('cliente_id')
            producto_id = item.get('producto_id')
            producto_detalle = item.get('producto_detalle')
            
            # Todos los importes monetarios deben cuantizarse estrictamente a 2 decimales
            tarifa_f = Decimal(str(item.get('tarifa_f', 0) or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tarifa_p = Decimal(str(item.get('tarifa_p', 0) or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            alic_iva = Decimal(str(item.get('alic_iva', 21.0) or 21.0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            
            msg_f = ""
            msg_p = ""
            advertencias = []
            
            try:
                cliente = ClienteProveedor.objects.get(pk=cliente_id)
                producto = Producto.objects.get(pk=producto_id)
                tarifa_obj = TarifaEstudio.objects.get(pk=id_tarifa)
                
                # Advertencias de gestión / auto-envío
                if not cliente.correo or not cliente.correo.strip():
                    advertencias.append("Sin correo electrónico para auto-envío")
                
                # Validar imputación contable
                cuenta_imputacion = tarifa_obj.cuenta or (producto.rubro.cta_ventas if producto.rubro else None)
                if not cuenta_imputacion:
                    advertencias.append("Sin cuenta contable de ventas asignada")
                
                # Si el cliente no tiene condición fiscal, derivar todo a comprobante interno
                if cliente.condicion_iva in ['PRESUPUESTO', 'CONSUMO INTERNO'] and tarifa_f > 0:
                    tarifa_p = (tarifa_p + tarifa_f).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    tarifa_f = Decimal('0.00')
                    
                # 1. Comprobante FISCAL (tarifa_f)
                total_f = Decimal('0.00')
                iva_calculado = Decimal('0.00')
                tipo_fiscal = None
                
                if tarifa_f > 0:
                    # Resolver tipo fiscal según condición IVA del receptor:
                    # - RI o Monotributo -> Factura A ('001')
                    # - Exento o Consumidor Final -> Factura B ('006')
                    from facturacion.views import resolver_tipo_comprobante_fiscal
                    tipo_fiscal = resolver_tipo_comprobante_fiscal(cliente.condicion_iva)
                    if not tipo_fiscal:
                        codigo_fallback = '001' if cliente.condicion_iva in ['RESPONSABLE INSCRIPTO', 'MONOTRIBUTO'] else '006'
                        tipo_fiscal = TipoComprobante.objects.filter(codigo=codigo_fallback).first()
                        
                    if not tipo_fiscal:
                        raise Exception(f"No se encontró Tipo Comprobante fiscal para el cliente {cliente.razon_social} ({cliente.condicion_iva})")

                    iva_calculado = (tarifa_f * (alic_iva / Decimal('100.0'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    total_f = (tarifa_f + iva_calculado).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                    # Validación de documento fiscal según reglas ARCA (DocTipo 80/96/99 y longitud de CUIT)
                    doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(cliente)

                    # Modo prueba: validación pura (Dry-Run) 100% en memoria sin persistir en BD
                    if modo_prueba:
                        msg_f = f"SIMULACIÓN: {tipo_fiscal.detalle} Pto {numero_pto:04d} Total ${total_f:,.2f} (Neto ${tarifa_f:,.2f} + IVA ${iva_calculado:,.2f})"
                    else:
                        # Emisión real a ARCA con Concepto=2 (Servicios)
                        id_iva_afip = 5 # 21% default
                        if alic_iva == Decimal('10.50'): id_iva_afip = 4
                        elif alic_iva == Decimal('27.00'): id_iva_afip = 6
                        elif alic_iva == Decimal('0.00'): id_iva_afip = 3
                        
                        alicuotas_list = [{
                            'id_iva': id_iva_afip,
                            'alicuota': float(alic_iva),
                            'base_imponible': float(tarifa_f),
                            'importe_iva': float(iva_calculado)
                        }]

                        datos_afip = {
                            'pto_vta': numero_pto,
                            'cbte_tipo': int(tipo_fiscal.codigo),
                            'concepto': 2,
                            'doc_tipo': doc_tipo,
                            'doc_nro': doc_nro,
                            'cbte_fch': fecha_cbte_str,
                            'imp_total': float(total_f),
                            'imp_tot_conc': 0.0,
                            'imp_neto': float(tarifa_f),
                            'imp_op_ex': 0.0,
                            'imp_iva': float(iva_calculado),
                            'condicion_iva_receptor_id': cond_iva_rec,
                            'mon_id': 'PES',
                            'mon_cotiz': 1.0,
                            'fch_serv_desde': fch_serv_desde.strftime('%Y%m%d'),
                            'fch_serv_hasta': fch_serv_hasta.strftime('%Y%m%d'),
                            'fch_vto_pago': fch_vto_pago.strftime('%Y%m%d')
                        }
                        
                        afip_service = AFIPService(empresa_obj)
                        res_afip = afip_service.emitir_comprobante(datos_afip, alicuotas_list)
                        
                        if not res_afip.get('exito'):
                            raise Exception(f"Error AFIP para {cliente.razon_social}: {res_afip.get('error')}")
                        
                        with transaction.atomic():
                            venta_f = Venta(
                                empresa_id=self.empresa_id,
                                fecha=timezone.localdate(),
                                periodo=periodo,
                                periodo_facturado=periodo,
                                tipo=tipo_fiscal,
                                condic=1,
                                punto=numero_pto,
                                numero=res_afip['numero_comprobante'],
                                cliente=cliente,
                                cliente_razon_social=cliente.razon_social,
                                cliente_cuit=cliente.cuit,
                                moneda='PES',
                                cotizacion=1.0,
                                neto=tarifa_f,
                                iva=iva_calculado,
                                total=total_f,
                                usuario=self.usuario,
                                sucursal_id=sucursal_id,
                                cae=res_afip['cae'],
                                vto_cae=res_afip['vto_cae'],
                                cod_qr=res_afip.get('cod_qr')
                            )
                            venta_f.save()
                            
                            # VentaItem
                            VentaItem.objects.create(
                                venta=venta_f,
                                producto=producto,
                                concepto=producto_detalle,
                                cantidad=1,
                                precio_unitario=tarifa_f,
                                iva_alicuota=alic_iva,
                                total=total_f
                            )
                            
                            MovimientoStock.objects.create(
                                producto=producto,
                                sucursal_id=sucursal_id,
                                tipo='SALIDA',
                                cantidad=1,
                                creado_por=self.usuario
                            )
                            
                            VentaAlicuotaIva.objects.create(
                                venta=venta_f,
                                id_iva=id_iva_afip,
                                alicuota=alic_iva,
                                base_imponible=tarifa_f,
                                importe_iva=iva_calculado
                            )

                            # Re-guardar para que se dispare la señal contable
                            venta_f.save()

                            # Registrar en cola de envíos de Estudio
                            EnvioFacturaEstudio.objects.update_or_create(
                                venta=venta_f,
                                defaults={
                                    'empresa_id': self.empresa_id,
                                    'cliente': cliente,
                                    'periodo': periodo,
                                    'destinatarios': cliente.correo or '',
                                    'estado': 'PENDIENTE',
                                    'creado_por': self.usuario,
                                    'modificado_por': self.usuario,
                                }
                            )

                        msg_f = f"FISCAL: {tipo_fiscal.detalle} {numero_pto:04d}-{venta_f.numero:08d} Generada."
                
                # 2. Comprobante INTERNO (tarifa_p)
                if tarifa_p > 0:
                    if not tipo_interno:
                        tipo_interno = TipoComprobante.objects.filter(estado=True).first()
                        
                    if modo_prueba:
                        msg_p = f"SIMULACIÓN: {tipo_interno.detalle} Total ${tarifa_p:,.2f}"
                    else:
                        with transaction.atomic():
                            numero_fact_p = siguiente_numero_pre(self.empresa_id, punto_interno)

                            venta_p = Venta(
                                empresa_id=self.empresa_id,
                                fecha=timezone.localdate(),
                                periodo=periodo,
                                periodo_facturado=periodo,
                                tipo=tipo_interno,
                                condic=2,
                                punto=punto_interno,
                                numero=numero_fact_p,
                                cliente=cliente,
                                cliente_razon_social=cliente.razon_social,
                                cliente_cuit=cliente.cuit,
                                moneda='PES',
                                cotizacion=1.0,
                                neto=tarifa_p,
                                iva=Decimal('0.00'),
                                total=tarifa_p,
                                usuario=self.usuario,
                                sucursal_id=sucursal_id
                            )
                            venta_p.save()
                            
                            VentaItem.objects.create(
                                venta=venta_p,
                                producto=producto,
                                concepto=producto_detalle,
                                cantidad=1,
                                precio_unitario=tarifa_p,
                                iva_alicuota=Decimal('0.00'),
                                total=tarifa_p
                            )
                            
                            MovimientoStock.objects.create(
                                producto=producto,
                                sucursal_id=sucursal_id,
                                tipo='SALIDA',
                                cantidad=1,
                                creado_por=self.usuario
                            )

                            venta_p.save()

                            # Registrar en cola de envíos de Estudio
                            EnvioFacturaEstudio.objects.update_or_create(
                                venta=venta_p,
                                defaults={
                                    'empresa_id': self.empresa_id,
                                    'cliente': cliente,
                                    'periodo': periodo,
                                    'destinatarios': cliente.correo or '',
                                    'estado': 'PENDIENTE',
                                    'creado_por': self.usuario,
                                    'modificado_por': self.usuario,
                                }
                            )

                        msg_p = f"INTERNO: {tipo_interno.detalle} {punto_interno:04d}-{numero_fact_p:08d} Generada."
                
                self.resultados.append({
                    'id_tarifa': id_tarifa,
                    'cliente_id': cliente.codigo_id,
                    'razon_social': cliente.razon_social,
                    'cuit': cliente.cuit or '',
                    'condicion_iva': cliente.condicion_iva,
                    'status': 'success',
                    'tarifa_f': float(tarifa_f),
                    'iva_f': float(iva_calculado),
                    'total_f': float(total_f),
                    'tarifa_p': float(tarifa_p),
                    'msg_f': msg_f,
                    'msg_p': msg_p,
                    'advertencias': advertencias
                })
            
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.resultados.append({
                    'id_tarifa': id_tarifa,
                    'cliente_id': cliente_id,
                    'razon_social': item.get('razon_social', f"Cliente {cliente_id}"),
                    'cuit': item.get('cuit', ''),
                    'condicion_iva': item.get('condicion_iva', ''),
                    'status': 'error',
                    'tarifa_f': float(tarifa_f),
                    'iva_f': float(0),
                    'total_f': float(tarifa_f),
                    'tarifa_p': float(tarifa_p),
                    'msg': str(ex),
                    'advertencias': advertencias
                })

        return self.resultados

