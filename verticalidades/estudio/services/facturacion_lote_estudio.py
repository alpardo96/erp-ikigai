from decimal import Decimal
import calendar
from datetime import date

from core.services.numeracion import siguiente_numero_pre
from django.db import transaction
from django.utils import timezone
from facturacion.models import Venta, VentaItem, VentaAlicuotaIva, ClienteProveedor, TipoComprobante
from verticalidades.estudio.models import TarifaEstudio
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
            tarifa_f = Decimal(str(item.get('tarifa_f', 0)))
            tarifa_p = Decimal(str(item.get('tarifa_p', 0)))
            alic_iva = Decimal(str(item.get('alic_iva', 21.0)))
            
            msg_f = ""
            msg_p = ""
            
            try:
                # Todo debe ir en atomic por cada comprobante o por el lote. 
                # Lo ponemos por iteración para que si uno falla no cancele todo el lote, sino solo ese cliente.
                with transaction.atomic():
                    cliente = ClienteProveedor.objects.get(pk=cliente_id)
                    producto = Producto.objects.get(pk=producto_id)
                    tarifa_obj = TarifaEstudio.objects.get(pk=id_tarifa)
                    
                    # Si el cliente no tiene condición fiscal, derivar todo a comprobante interno
                    if cliente.condicion_iva in ['PRESUPUESTO', 'CONSUMO INTERNO'] and tarifa_f > 0:
                        tarifa_p += tarifa_f
                        tarifa_f = Decimal('0')
                        
                    # 1. Comprobante FISCAL (tarifa_f)
                    if tarifa_f > 0:
                        codigo_tipo = '011' # C por defecto
                        if cliente.condicion_iva == 'RESPONSABLE INSCRIPTO':
                            codigo_tipo = '001' # A
                        elif cliente.condicion_iva in ['MONOTRIBUTO', 'EXENTO', 'CONSUMIDOR FINAL']:
                            codigo_tipo = '006' # B
                            
                        tipo_fiscal = TipoComprobante.objects.filter(codigo=codigo_tipo).first()
                        if not tipo_fiscal:
                            raise Exception(f"No se encontró Tipo Comprobante para código {codigo_tipo}")

                        iva_calculado = tarifa_f * (alic_iva / Decimal('100.0'))
                        total_f = tarifa_f + iva_calculado

                        venta_f = Venta(
                            empresa_id=self.empresa_id,
                            fecha=timezone.localdate(),
                            periodo=periodo,
                            periodo_facturado=periodo,
                            tipo=tipo_fiscal,
                            condic=1,
                            punto=numero_pto,
                            numero=0,  # Se setea luego con lo que devuelve ARCA
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
                        )
                        
                        id_iva_afip = 5 # 21% default
                        if alic_iva == Decimal('10.5'): id_iva_afip = 4
                        elif alic_iva == Decimal('27.0'): id_iva_afip = 6
                        elif alic_iva == Decimal('0.0'): id_iva_afip = 3
                        
                        alicuotas_list = [{
                            'id_iva': id_iva_afip,
                            'alicuota': alic_iva,
                            'base_imponible': float(tarifa_f),
                            'importe_iva': float(iva_calculado)
                        }]
                        
                        doc_tipo, doc_nro, cond_iva_rec = validar_y_obtener_documento_receptor(cliente)

                        # Modo prueba usa datos ficticios sin emitir, caso contrario ARCA
                        if modo_prueba:
                            venta_f.cae = "12345678901234"
                            venta_f.vto_cae = timezone.localdate()
                            ultimo_num = Venta.objects.filter(empresa_id=self.empresa_id, tipo=tipo_fiscal, punto=numero_pto).order_by('-numero').first()
                            venta_f.numero = (ultimo_num.numero + 1) if ultimo_num else 1
                        else:
                            # Emisión real a ARCA con Concepto=2 (Servicios)
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
                                
                            venta_f.cae = res_afip['cae']
                            venta_f.vto_cae = res_afip['vto_cae']
                            venta_f.numero = res_afip['numero_comprobante']
                            venta_f.cod_qr = res_afip.get('cod_qr')

                        # Guardar la venta tras tener número y CAE
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

                        # Re-guardar para que se dispare la señal contable, que requiere que existan ítems.
                        venta_f.save()

                        msg_f = f"FISCAL: {tipo_fiscal.detalle} {numero_pto:04d}-{venta_f.numero:08d} Generada."
                    
                    # 2. Comprobante INTERNO (tarifa_p)
                    if tarifa_p > 0:
                        if not tipo_interno:
                            tipo_interno = TipoComprobante.objects.filter(estado=True).first()
                            
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
                            iva=0,
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
                            iva_alicuota=0,
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

                        msg_p = f"INTERNO: {tipo_interno.detalle} {punto_interno:04d}-{numero_fact_p:08d} Generada."
                    
                    self.resultados.append({
                        'id_tarifa': id_tarifa,
                        'status': 'success',
                        'msg_f': msg_f,
                        'msg_p': msg_p
                    })
                
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.resultados.append({
                    'id_tarifa': id_tarifa,
                    'status': 'error',
                    'msg': str(ex)
                })

        return self.resultados
