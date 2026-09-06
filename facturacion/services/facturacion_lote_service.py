from decimal import Decimal

from core.services.numeracion import siguiente_numero_pre
from django.db import transaction
from django.utils import timezone
from facturacion.models import Venta, VentaItem, VentaAlicuotaIva, ClienteProveedor, TipoComprobante
from verticalidades.estudio.models import TarifaEstudio
from productos.models import Producto, MovimientoStock, Sucursal
from contable.models import Asiento, AsientoLinea, Cuenta, ParametrosContables

# Usamos la señal o función manual
# En este sistema ya existe un mecanismo automático, pero podemos forzar _no_contabilizar=True
# y hacerlo nosotros si queremos, o dejar que la señal trabaje sola.
# La señal usa contable.services.contabilizacion.contabilizar_venta_individual.

class FacturacionLoteService:
    def __init__(self, empresa_id, usuario):
        self.empresa_id = empresa_id
        self.usuario = usuario
        self.resultados = []

    def procesar_lote(self, lote_datos, periodo, pto_vta_id, modo_prueba=True):
        self.resultados = []
        
        # Plan 075: sin fallbacks silenciosos. Un comprobante mal numerado o emitido bajo
        # un tipo elegido por descarte es peor que un comprobante no emitido: sale igual,
        # nadie se entera, y el problema aparece meses después en una auditoría.
        tipo_interno = TipoComprobante.objects.filter(codigo='PRE').first()
        if not tipo_interno:
            raise ValueError(
                "Falta configurar el tipo de comprobante 'PRE' (Comprobante Interno). "
                "Cargalo en Configuración → Tipos de Comprobante antes de facturar.")

        from empresas.models import PuntoVenta
        pto_vta_obj = PuntoVenta.objects.filter(
            id=pto_vta_id, empresa_id=self.empresa_id).select_related('sucursal').first()
        if not pto_vta_obj:
            raise ValueError(
                "No se pudo resolver el punto de venta indicado para esta empresa. "
                "Verificá la configuración de Puntos de Venta.")

        # Serie FISCAL: la gobierna ARCA y se emite por el punto de venta autorizado.
        numero_pto = pto_vta_obj.numero
        sucursal_id = pto_vta_obj.sucursal_id
        if not sucursal_id:
            raise ValueError("El punto de venta no tiene sucursal asociada.")

        # Serie NO FISCAL: el punto es la sucursal emisora, y el número lo da el
        # contador transaccional, no una lectura del último emitido.
        punto_interno = sucursal_id

        with transaction.atomic():
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
                    cliente = ClienteProveedor.objects.get(pk=cliente_id)
                    producto = Producto.objects.get(pk=producto_id)
                    tarifa_obj = TarifaEstudio.objects.get(pk=id_tarifa)
                    
                    # 1. Comprobante FISCAL (tarifa_f)
                    if tarifa_f > 0:
                        # Determinar tipo fiscal según cliente
                        codigo_tipo = '011' # C por defecto
                        if cliente.condicion_iva == 'RESPONSABLE INSCRIPTO':
                            codigo_tipo = '001' # A
                        elif cliente.condicion_iva in ['MONOTRIBUTO', 'EXENTO', 'CONSUMIDOR FINAL']:
                            codigo_tipo = '006' # B
                            
                        tipo_fiscal = TipoComprobante.objects.filter(codigo=codigo_tipo).first()
                        if not tipo_fiscal:
                            raise Exception(f"No se encontró Tipo Comprobante para código {codigo_tipo}")

                        # Buscar último número de comprobante para ese punto y tipo en la DB
                        # Idealmente ARCA nos dice cuál es, pero en modo prueba lo calculamos
                        ultimo_num = Venta.objects.filter(empresa_id=self.empresa_id, tipo=tipo_fiscal, punto=numero_pto).order_by('-numero').first()
                        numero_fact = (ultimo_num.numero + 1) if ultimo_num else 1

                        iva_calculado = tarifa_f * (alic_iva / Decimal('100.0'))
                        total_f = tarifa_f + iva_calculado

                        # Crear Venta
                        venta_f = Venta(
                            empresa_id=self.empresa_id,
                            fecha=timezone.localdate(),
                            periodo=periodo,
                            periodo_facturado=periodo,
                            tipo=tipo_fiscal,
                            # FISCAL. Coincide con el default, pero se declara explícito
                            # para que el par fiscal/no fiscal se lea de un vistazo.
                            condic=1,
                            punto=numero_pto,
                            numero=numero_fact,
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
                            #_no_contabilizar=True # Si quisiéramos evitar la señal
                        )
                        
                        if modo_prueba:
                            # CAE ficticio: sirve para probar el circuito sin tocar ARCA.
                            # NO debe usarse en producción — un comprobante con este CAE
                            # figura como autorizado y no lo está.
                            venta_f.cae = "12345678901234"
                            venta_f.vto_cae = timezone.localdate()
                        else:
                            # Emisión real: el número y el CAE los da ARCA
                            # (`AfipService` ya implementa FECompUltimoAutorizado y toma
                            # el número de `CbteDesde`). Todavía no está cableado acá:
                            # se corta antes de emitir en vez de generar un comprobante
                            # con numeración local que ARCA no autorizó.
                            raise ValueError(
                                "La emisión real contra ARCA todavía no está habilitada "
                                "en la facturación por lote. Falta cablear AfipService "
                                "(Plan 075 §5.3).")
                        
                        venta_f.save() # La señal debería encargarse de contabilidad y stock
                        
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
                        
                        # VentaAlicuotaIva
                        id_iva_afip = 5 # 21% default
                        if alic_iva == Decimal('10.5'): id_iva_afip = 4
                        elif alic_iva == Decimal('27.0'): id_iva_afip = 6
                        elif alic_iva == Decimal('0.0'): id_iva_afip = 3
                        
                        VentaAlicuotaIva.objects.create(
                            venta=venta_f,
                            id_iva=id_iva_afip,
                            alicuota=alic_iva,
                            base_imponible=tarifa_f,
                            importe_iva=iva_calculado
                        )

                        # La señal contabiliza en el `post_save` de la Venta, pero acá ese
                        # save ocurrió ANTES de crear los ítems y
                        # `contabilizar_venta_individual` corta con
                        # `if not venta.items.exists(): return None`. Sin este
                        # re-guardado la factura quedaba EMITIDA Y SIN ASIENTO.
                        venta_f.save()

                        msg_f = f"FISCAL: {tipo_fiscal.detalle} {numero_pto:04d}-{numero_fact:08d} Generada."
                    
                    # 2. Comprobante INTERNO (tarifa_p)
                    if tarifa_p > 0:
                        if not tipo_interno:
                            tipo_interno = TipoComprobante.objects.filter(estado=True).first() # Fallback a cualquiera
                            
                        # Plan 075: contador con `select_for_update()`. El patrón
                        # anterior —leer el último y sumarle uno— no resiste dos lotes
                        # simultáneos, y esta serie no tiene ninguna autoridad externa
                        # que corrija un duplicado.
                        numero_fact_p = siguiente_numero_pre(self.empresa_id, punto_interno)

                        venta_p = Venta(
                            empresa_id=self.empresa_id,
                            fecha=timezone.localdate(),
                            periodo=periodo,
                            periodo_facturado=periodo,
                            tipo=tipo_interno,
                            # NO FISCAL. Sin esto quedaba con el default (1 = Real) y el
                            # comprobante decía ser fiscal mientras su asiento decía lo
                            # contrario. Hoy no llega al Libro IVA sólo porque
                            # `_no_contabilizar` corta la señal entera, pero cualquier
                            # re-guardado sin ese flag dispara
                            # `contabilizar_venta_individual`, que puebla el Libro IVA
                            # cuando `condic in (1, 3)`: una operación inexistente para
                            # el fisco terminaría declarada. Además cualquier reporte
                            # que filtre por `Venta.condic` contaba el interno como
                            # fiscal.
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

                        # El asiento lo genera `contabilizar_venta_individual` a través
                        # de la señal, igual que cualquier otra venta del sistema. Antes
                        # se armaba a mano acá —unas 60 líneas— para compensar que el
                        # comprobante estaba mal marcado como fiscal.
                        #
                        # Delegar resuelve tres cosas de una: la cuenta patrimonial sale
                        # de `cliente.cta_pat` con fallback a
                        # `ParametrosContables.cta_clientes_default`; la de resultado sale
                        # del RUBRO del producto facturado con fallback a
                        # `parametros.cta_ventas`; y si falta alguna, se levanta un error
                        # explícito en lugar de emitir el comprobante sin registración.
                        venta_p.save()

                        msg_p = f"INTERNO: {tipo_interno.detalle} {punto_interno:04d}-{numero_fact_p:08d} Generada."
                    
                    self.resultados.append({
                        'id_tarifa': id_tarifa,
                        'status': 'success',
                        'msg_f': msg_f,
                        'msg_p': msg_p
                    })
                
                except Exception as ex:
                    # En lugar de fallar todo el bloque y hacer rollback de todos los clientes, 
                    # idealmente guardamos el error, pero al usar with transaction.atomic() afuera, 
                    # si relanzamos, falla todo. Si NO relanzamos, se guardan los exitosos y reporta error el resto.
                    # Voy a reportar el error en la lista para que el front lo muestre sin relanzar.
                    import traceback
                    traceback.print_exc()
                    self.resultados.append({
                        'id_tarifa': id_tarifa,
                        'status': 'error',
                        'msg': str(ex)
                    })

        return self.resultados
