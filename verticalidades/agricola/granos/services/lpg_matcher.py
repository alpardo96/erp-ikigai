"""
Servicio de cotejo, validación y resolución de mapeos para Liquidaciones Primarias de Granos (LPG).

Verifica:
1. Control de duplicados por COE en Venta / LibroIvaVentas.
2. Resolución del Comprador en ClienteProveedor por CUIT.
3. Resolución del Cultivo en GranoMapeo por código ARCA (ej. 19 -> Maíz -> Cta 51).
4. Resolución de cada concepto de deducción en GastoMapeo por patrón (ej. FLETE -> Cta Fletes).
5. Detección de conceptos nuevos no catalogados para auto-aprendizaje.
6. Carga de parámetros contables impositivos (IVA Débito, IVA Crédito, Retenciones).
"""
from decimal import Decimal
from django.db.models import Q
from facturacion.models import ClienteProveedor, Venta
from contable.models import ParametrosContables, Cuenta
from verticalidades.agricola.granos.models import GranoMapeo, GastoMapeo


class LpgMatcher:
    """
    Motor de cotejo de datos extraídos del PDF contra los maestros del ERP.
    """

    @classmethod
    def match_liquidaciones(cls, empresa, parsed_list):
        """
        Procesa una lista de diccionarios devueltos por LpgPdfParser y los enriquece
        con las relaciones del ERP, banderas de duplicados y estados de validación.
        """
        # Cargar parámetros contables de la empresa
        params_contables = ParametrosContables.objects.filter(empresa=empresa).first()
        
        # Cargar mapeos de granos y gastos vigentes para la empresa
        granos_mapeos = {gm.codigo_arca: gm for gm in GranoMapeo.objects.filter(empresa=empresa).select_related('producto', 'cta_ventas')}
        gastos_mapeos = list(GastoMapeo.objects.filter(empresa=empresa).select_related('cta_gasto'))

        resultados = []
        for parsed in parsed_list:
            res = cls.match_single(empresa, parsed, granos_mapeos, gastos_mapeos, params_contables)
            resultados.append(res)

        return resultados

    @classmethod
    def match_single(cls, empresa, parsed, granos_mapeos=None, gastos_mapeos=None, params_contables=None):
        """
        Coteja una única liquidación parsed contra el ERP.
        """
        if granos_mapeos is None:
            granos_mapeos = {gm.codigo_arca: gm for gm in GranoMapeo.objects.filter(empresa=empresa).select_related('producto', 'cta_ventas')}
        if gastos_mapeos is None:
            gastos_mapeos = list(GastoMapeo.objects.filter(empresa=empresa).select_related('cta_gasto'))
        if params_contables is None:
            params_contables = ParametrosContables.objects.filter(empresa=empresa).first()

        item_match = {
            'parsed': parsed,
            'estado': 'LISTO',  # 'LISTO', 'REQUIERE_CONFIGURACION', 'DUPLICADO'
            'es_duplicado': False,
            'comprobante_existente': None,
            'comprador_match': None,
            'requiere_crear_comprador': False,
            'grano_match': None,
            'requiere_mapeo_grano': False,
            'deducciones_matched': [],
            'gastos_nuevos_detectados': [],
            'retenciones_matched': [],
            'params_contables_ok': bool(params_contables),
            'mensajes_advertencia': []
        }

        # 1. Control de No Duplicación por C.O.E.
        coe = parsed.get('coe', '').strip()
        if coe:
            venta_existente = Venta.objects.filter(empresa=empresa, cae=coe).select_related('cliente', 'tipo').first()
            if venta_existente:
                item_match['es_duplicado'] = True
                item_match['estado'] = 'DUPLICADO'
                item_match['comprobante_existente'] = {
                    'ventas_id': venta_existente.ventas_id,
                    'asiento_id': venta_existente.asiento_id,
                    'fecha': venta_existente.fecha.strftime('%d/%m/%Y'),
                    'tipo': str(venta_existente.tipo),
                    'total': str(venta_existente.total)
                }
                item_match['mensajes_advertencia'].append(
                    f"Comprobante ya registrado previamente (COE: {coe} | Venta #{venta_existente.ventas_id} | Asiento #{venta_existente.asiento_id})"
                )
                return item_match

        # 2. Match de Comprador / Cliente
        cuit_comp = parsed.get('comprador', {}).get('cuit', '').strip()
        if cuit_comp:
            cliente = ClienteProveedor.objects.filter(empresa=empresa, cuit=cuit_comp).first()
            if not cliente and len(cuit_comp) == 11:
                # Intentar buscar sin ceros iniciales o formato flexible
                cliente = ClienteProveedor.objects.filter(empresa=empresa, cuit__contains=cuit_comp).first()

            if cliente:
                item_match['comprador_match'] = {
                    'codigo_id': cliente.codigo_id,
                    'razon_social': cliente.razon_social,
                    'cuit': cliente.cuit,
                    'cta_pat': cliente.cta_pat,
                    'condicion_iva': cliente.condicion_iva
                }
                if not cliente.cta_pat:
                    item_match['mensajes_advertencia'].append(
                        f"El cliente {cliente.razon_social} no tiene Cuenta Patrimonial (cta_pat) asignada. Se requerirá indicar una."
                    )
                    item_match['estado'] = 'REQUIERE_CONFIGURACION'
            else:
                item_match['requiere_crear_comprador'] = True
                item_match['estado'] = 'REQUIERE_CONFIGURACION'
                item_match['mensajes_advertencia'].append(
                    f"Comprador no registrado en Clientes (CUIT: {cuit_comp} - {parsed.get('comprador', {}).get('razon_social')}). Se creará en el alta."
                )

        # 3. Match de Grano / Cultivo
        cod_grano = parsed.get('grano', {}).get('codigo_arca', 0)
        grano_mapeado = granos_mapeos.get(cod_grano)
        if grano_mapeado:
            item_match['grano_match'] = {
                'codigo_arca': grano_mapeado.codigo_arca,
                'descripcion_arca': grano_mapeado.descripcion_arca,
                'producto_id': grano_mapeado.producto_id,
                'producto_detalle': grano_mapeado.producto.detalle,
                'cta_ventas_id': grano_mapeado.cta_ventas_id,
                'cta_ventas_nombre': f"{grano_mapeado.cta_ventas.jerarquia} - {grano_mapeado.cta_ventas.cuenta}"
            }
        else:
            item_match['requiere_mapeo_grano'] = True
            item_match['estado'] = 'REQUIERE_CONFIGURACION'
            item_match['mensajes_advertencia'].append(
                f"Cultivo ARCA [{cod_grano}] {parsed.get('grano', {}).get('descripcion_arca')} no tiene producto ni cuenta de ventas asignada."
            )

        # 4. Match de Deducciones / Gastos
        import unicodedata

        def _normalizar(texto):
            if not texto:
                return ""
            return unicodedata.normalize('NFKD', str(texto)).encode('ASCII', 'ignore').decode('utf-8').upper().strip()

        for ded in parsed.get('deducciones', []):
            concepto_norm = _normalizar(ded['concepto'])
            gasto_matched = None
            
            # Buscar por patrón de subcadena
            for gm in gastos_mapeos:
                patron_norm = _normalizar(gm.patron)
                if patron_norm and patron_norm in concepto_norm:
                    gasto_matched = gm
                    break

            if gasto_matched:
                item_match['deducciones_matched'].append({
                    'concepto_original': ded['concepto'],
                    'tipo_deduccion': ded['tipo_deduccion'],
                    'base_calculo': ded['base_calculo'],
                    'alicuota_iva': ded['alicuota_iva'],
                    'importe_iva': ded['importe_iva'],
                    'total': ded['total'],
                    'cta_gasto_id': gasto_matched.cta_gasto_id,
                    'cta_gasto_nombre': f"{gasto_matched.cta_gasto.jerarquia} - {gasto_matched.cta_gasto.cuenta}",
                    'patron_coincidente': gasto_matched.patron,
                    'es_nuevo': False
                })
            else:
                # Concepto nuevo detectado
                nuevo_gasto = {
                    'concepto_original': ded['concepto'],
                    'tipo_deduccion': ded['tipo_deduccion'],
                    'base_calculo': ded['base_calculo'],
                    'alicuota_iva': ded['alicuota_iva'],
                    'importe_iva': ded['importe_iva'],
                    'total': ded['total'],
                    'cta_gasto_id': None,
                    'cta_gasto_nombre': None,
                    'es_nuevo': True
                }
                item_match['deducciones_matched'].append(nuevo_gasto)
                item_match['gastos_nuevos_detectados'].append(ded['concepto'])
                item_match['estado'] = 'REQUIERE_CONFIGURACION'
                item_match['mensajes_advertencia'].append(
                    f"Concepto de gasto no catalogado: '{ded['concepto']}'. Selecciona la cuenta contable respectiva."
                )

        # 5. Validación de Cuentas de Parámetros Contables
        if not params_contables or not params_contables.cta_iva_debito_id:
            item_match['mensajes_advertencia'].append("Falta configurar la Cuenta de IVA Débito Fiscal en Parámetros Contables.")
            item_match['estado'] = 'REQUIERE_CONFIGURACION'
        if parsed.get('deducciones') and (not params_contables or not params_contables.cta_iva_credito_id):
            item_match['mensajes_advertencia'].append("Falta configurar la Cuenta de IVA Crédito Fiscal en Parámetros Contables.")
            item_match['estado'] = 'REQUIERE_CONFIGURACION'
        if parsed.get('retenciones') and (not params_contables or not params_contables.cta_ret_iva_id):
            item_match['mensajes_advertencia'].append("Falta configurar la Cuenta de Retenciones Sufridas IVA en Parámetros Contables.")
            item_match['estado'] = 'REQUIERE_CONFIGURACION'

        return item_match
