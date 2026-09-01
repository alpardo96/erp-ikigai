"""Pantallas operativas del módulo Distribución (Plan 074)."""
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from empresas.models import Empresa
from facturacion.models import ClienteProveedor
from productos.models import Producto, StockSucursal

from .models import (CarteraVendedor, DiaVisita, MotivoDevolucion, Personal,
                     Reparto, RepartoParada, Vehiculo, ZonaReparto)
from .services.asignacion import (aplicar_asignacion, detectar_faltantes,
                                  hay_faltantes, sugerir_asignacion)
from .services.facturacion import (facturar_lote, pedidos_pendientes,
                                   previsualizar)
from .services.devoluciones import (cargar_items, conciliacion,
                                    confirmar_recepcion, crear_recepcion,
                                    emitir_nota_credito, marcar_entregada,
                                    marcar_no_entregada, paradas_por_recibir)
from .services.reparto import (agregar_parada_de_cobranza, agregar_paradas,
                               cerrar_reparto, comprobantes_sin_reparto, consolidado,
                               crear_reparto, hoja_de_ruta, quitar_parada,
                               totales_hoja_de_ruta)
from .services.caja_reparto import rendir as rendir_reparto
from .services.caja_reparto import recibir as recibir_rendicion
from .services.caja_reparto import resumen as resumen_caja
from .services.caja_reparto import (rendiciones_por_recibir, resumen_vendedor,
                                   sesion_abierta_del_vendedor, tesoreria_reparto)
from .services.caja_reparto import rendir_vendedor
from .services.cobranza_fifo import comprobantes_abiertos, saldo_fiscal, saldo_operativo
from .services.cobranza_fifo import planificar as planificar_cobranza
from .services.cobranza_fifo import registrar as registrar_cobranza
from .services.saldos_clientes import listado as listado_saldos
from .services.reporte_devoluciones import reporte as reporte_devoluciones

from django.views.generic import TemplateView

class DistribucionIndexView(LoginRequiredMixin, TemplateView):
    template_name = 'distribucion/index.html'

class DistribucionRequiredMixin(LoginRequiredMixin):
    """Corta el acceso si la empresa activa no es una distribuidora."""

    def dispatch(self, request, *args, **kwargs):
        empresa_id = request.session.get('empresa_id')
        if not Empresa.objects.filter(id=empresa_id, tipo_actividad='DISTRIBUIDORA').exists():
            messages.error(request, "El módulo de Distribución no está habilitado para esta empresa.")
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)


def _puede_asignar(usuario):
    """Repartir stock escaso decide qué cliente recibe menos: es decisión comercial."""
    perfil = getattr(usuario, 'perfil', None)
    return bool(usuario.is_staff or (perfil and (
        perfil.permiso_distribucion_asignar_stock or perfil.es_admin_sistema)))


class CarteraIndexView(DistribucionRequiredMixin, View):
    """Cartera de vendedores y agenda de visitas.

    Las dos cosas se editan en la misma pantalla porque se cargan juntas: cuando se define
    de quién es un cliente, se define también qué día se lo visita.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        q = (request.GET.get('q') or '').strip()
        vendedor_id = (request.GET.get('vendedor') or '').strip()
        sin_asignar = request.GET.get('sin_asignar') == '1'

        clientes = (ClienteProveedor.objects
                    .filter(empresa_id=empresa_id, tipo_entidad=1)
                    .select_related('distribuidora')
                    .prefetch_related('cartera__vendedor', 'domicilios_entrega__zona',
                                      'domicilios_entrega__dias_visita'))
        if q:
            clientes = clientes.filter(
                Q(razon_social__icontains=q) | Q(cuit__icontains=q))
            if q.isdigit():
                clientes = clientes | ClienteProveedor.objects.filter(
                    empresa_id=empresa_id, tipo_entidad=1, codigo_id=int(q))
        if vendedor_id:
            clientes = clientes.filter(cartera__vendedor_id=vendedor_id, cartera__activa=True)
        if sin_asignar:
            clientes = clientes.filter(cartera__isnull=True)

        contexto = {
            'clientes': clientes.distinct().order_by('razon_social')[:300],
            'vendedores': Personal.objects.filter(
                empresa_id=empresa_id, es_vendedor=True, activo=True).order_by('nombre'),
            'zonas': ZonaReparto.objects.filter(empresa_id=empresa_id, activa=True)
                                        .order_by('orden', 'nombre'),
            'dias': DiaVisita.DIAS,
            'frecuencias': DiaVisita.FRECUENCIAS,
            'q': q,
            'vendedor_id': vendedor_id,
            'sin_asignar': sin_asignar,
            'total_sin_asignar': ClienteProveedor.objects.filter(
                empresa_id=empresa_id, tipo_entidad=1, cartera__isnull=True).count(),
        }
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'distribucion/partials/cartera_filas.html', contexto)
        return render(request, 'distribucion/cartera.html', contexto)


class FaltantesIndexView(LoginRequiredMixin, View):
    """Reporte de faltantes: qué productos no alcanzan para cubrir todos los pedidos.

    Es la pantalla previa a la facturación por lote (Plan 074 §7.3). Muestra el déficit
    por producto y, al desplegar, quién lo pidió en orden de llegada.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccioná empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        faltantes = detectar_faltantes(empresa_id, sucursal_id)
        contexto = {
            'faltantes': faltantes,
            'total_faltantes': len(faltantes),
            'puede_asignar': _puede_asignar(request.user),
        }
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'distribucion/partials/faltantes_filas.html', contexto)
        return render(request, 'distribucion/faltantes.html', contexto)


class AsignacionStockView(LoginRequiredMixin, View):
    """Reparto del stock escaso de UN producto entre los pedidos que lo piden.

    La sugerencia es por ORDEN DE LLEGADA —el que pidió primero se sirve primero—, y es
    sólo un punto de partida: el usuario ajusta a mano y cada cambio queda auditado.
    """

    def get(self, request, producto_id):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')

        producto = get_object_or_404(Producto, id=producto_id, empresa_id=empresa_id)
        filas = sugerir_asignacion(empresa_id, sucursal_id, producto_id)
        fila_stock = (StockSucursal.objects
                      .filter(producto_id=producto_id, sucursal_id=sucursal_id)
                      .values('cantidad').first())

        return render(request, 'distribucion/modals/asignacion_form.html', {
            'producto': producto,
            'filas': filas,
            'stock': (fila_stock['cantidad'] if fila_stock else 0) or 0,
            'total_pedido': sum(f['cantidad'] for f in filas),
            'puede_asignar': _puede_asignar(request.user),
        })

    def post(self, request, producto_id):
        if not _puede_asignar(request.user):
            return HttpResponse(
                "<div class='p-4 text-red-600 font-bold'>No tenés permiso para asignar stock.</div>",
                status=403)

        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')

        asignaciones = {}
        for clave, valor in request.POST.items():
            if not clave.startswith('cantidad_'):
                continue
            item_id = clave.replace('cantidad_', '')
            asignaciones[item_id] = (valor or '0').replace('.', '').replace(',', '.')

        try:
            ajustes = aplicar_asignacion(
                empresa_id, sucursal_id, producto_id, asignaciones, request.user,
                observacion=request.POST.get('observacion') or None)
        except ValueError as error:
            return HttpResponse(
                f"<div class='p-4 text-red-600 font-bold'>{error}</div>", status=200)

        respuesta = HttpResponse()
        respuesta['HX-Trigger'] = json.dumps({'reloadFaltantes': True, 'cerrarModal': True})
        respuesta['HX-Reswap'] = 'none'
        return respuesta


def _puede_facturar(usuario):
    """Emitir comprobantes fiscales no es una tarea de carga: lleva permiso propio."""
    perfil = getattr(usuario, 'perfil', None)
    return bool(usuario.is_staff or (perfil and (
        getattr(perfil, 'permiso_distribucion_facturar_lote', False)
        or perfil.permiso_facturacion_carga_ventas
        or perfil.es_admin_sistema)))


class FacturacionLoteView(LoginRequiredMixin, View):
    """Facturación masiva de los pedidos del día (Plan 074 §7.4).

    GET  → grilla de previsualización: qué se va a emitir y con qué condición de venta.
    POST → emite los pedidos tildados y devuelve el resultado de cada uno.

    Se previsualiza antes de emitir a propósito: una vez emitido el comprobante fiscal,
    corregirlo cuesta una nota de crédito.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccioná empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        filas = previsualizar(empresa_id, sucursal_id)
        contexto = {
            'filas': filas,
            'total_pedidos': len(filas),
            'total_importe': sum(f['total'] for f in filas),
            'con_faltantes': hay_faltantes(empresa_id, sucursal_id),
            'puede_facturar': _puede_facturar(request.user),
        }
        if request.headers.get('HX-Request') == 'true':
            return render(request, 'distribucion/partials/facturacion_filas.html', contexto)
        return render(request, 'distribucion/facturacion.html', contexto)

    def post(self, request):
        if not _puede_facturar(request.user):
            return HttpResponse(
                "<div class='p-4 text-red-600 font-bold'>No tenés permiso para facturar.</div>",
                status=403)

        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')

        elegidos = set(request.POST.getlist('pedidos'))
        pedidos = [p for p in pedidos_pendientes(empresa_id, sucursal_id)
                   if str(p.id) in elegidos]

        if not pedidos:
            return render(request, 'distribucion/partials/facturacion_resultado.html',
                          {'error': "No seleccionaste ningún pedido."})

        resultados = facturar_lote(pedidos, request.user, modo_prueba=True)
        return render(request, 'distribucion/partials/facturacion_resultado.html', {
            'resultados': resultados,
            'emitidos': sum(1 for r in resultados if r['ok']),
            'fallidos': sum(1 for r in resultados if not r['ok']),
        })


class RepartoListView(LoginRequiredMixin, View):
    """Listado de repartos y alta de uno nuevo."""

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        if not empresa_id or not sucursal_id:
            messages.warning(request, "Seleccioná empresa y sucursal primero.")
            return redirect('seleccion_empresa')

        repartos = (Reparto.objects
                    .filter(empresa_id=empresa_id, sucursal_id=sucursal_id)
                    .select_related('vehiculo', 'zona')
                    .prefetch_related('responsables', 'paradas'))
        return render(request, 'distribucion/repartos.html', {
            'repartos': repartos[:100],
            'pendientes': comprobantes_sin_reparto(empresa_id, sucursal_id).count(),
            'vehiculos': Vehiculo.objects.filter(empresa_id=empresa_id, activo=True),
            'zonas': ZonaReparto.objects.filter(empresa_id=empresa_id, activa=True),
            'repartidores': Personal.objects.filter(
                empresa_id=empresa_id, es_repartidor=True, activo=True),
        })

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')

        reparto = crear_reparto(
            empresa_id, sucursal_id, request.user,
            vehiculo=Vehiculo.objects.filter(
                id=request.POST.get('vehiculo') or 0, empresa_id=empresa_id).first(),
            zona=ZonaReparto.objects.filter(
                id=request.POST.get('zona') or 0, empresa_id=empresa_id).first(),
            responsables=Personal.objects.filter(
                id__in=request.POST.getlist('responsables'), empresa_id=empresa_id),
            observaciones=request.POST.get('observaciones') or None)

        messages.success(request, f"Reparto N° {reparto.numero} creado. Agregale los comprobantes a cargar.")
        return redirect('distribucion_reparto_detalle', reparto_id=reparto.id)


class RepartoDetalleView(LoginRequiredMixin, View):
    """Armado del reparto: qué comprobantes se cargan al vehículo."""

    def get(self, request, reparto_id):
        empresa_id = request.session.get('empresa_id')
        reparto = get_object_or_404(Reparto, id=reparto_id, empresa_id=empresa_id)
        filas, totales_cons = consolidado(reparto)

        return render(request, 'distribucion/reparto_detalle.html', {
            'reparto': reparto,
            'paradas': hoja_de_ruta(reparto),
            'disponibles': comprobantes_sin_reparto(
                empresa_id, reparto.sucursal_id,
                zona_id=reparto.zona_id) if reparto.editable else [],
            'consolidado': filas,
            'totales_consolidado': totales_cons,
            'totales': totales_hoja_de_ruta(reparto),
            'clientes_con_saldo': (_clientes_con_saldo(empresa_id, reparto)
                                   if reparto.editable else []),
        })

    def post(self, request, reparto_id):
        from verticalidades.distribucion.models import ExtensionPedidoDistribucion

        empresa_id = request.session.get('empresa_id')
        reparto = get_object_or_404(Reparto, id=reparto_id, empresa_id=empresa_id)
        accion = request.POST.get('accion')

        try:
            if accion == 'agregar':
                pedidos = ExtensionPedidoDistribucion.objects.filter(
                    id__in=request.POST.getlist('pedidos'),
                    preventa__empresa_id=empresa_id)
                agregados = agregar_paradas(reparto, pedidos, request.user)
                messages.success(request, f"{agregados} comprobante(s) agregado(s) al reparto.")
            elif accion == 'agregar_cobranza':
                # Un cliente con saldo que NO hizo pedido. El repartidor pasa sólo a
                # cobrarle: sin mercadería no hay cobro mínimo que exigir (Plan 076 §A).
                cliente = get_object_or_404(
                    ClienteProveedor, codigo_id=request.POST.get('cliente'),
                    empresa_id=empresa_id)
                agregar_parada_de_cobranza(reparto, cliente, request.user)
                messages.success(
                    request,
                    f"{cliente.razon_social} agregado como parada de sólo cobranza. "
                    "Se imprime su saldo como dato, sin cobro mínimo.")
            elif accion == 'quitar':
                parada = get_object_or_404(
                    RepartoParada, id=request.POST.get('parada'), reparto=reparto)
                quitar_parada(parada)
                messages.success(request, "Parada quitada del reparto.")
            elif accion == 'cerrar':
                cerrar_reparto(reparto, request.user)
                messages.success(
                    request,
                    f"Reparto N° {reparto.numero} cerrado. Ya podés imprimir la Hoja de "
                    "Ruta y el Consolidado.")
        except ValueError as error:
            messages.error(request, str(error))

        return redirect('distribucion_reparto_detalle', reparto_id=reparto.id)


def _clientes_con_saldo(empresa_id, reparto):
    """Candidatos a parada de sólo cobranza: deben plata y no están ya en el reparto."""
    ya_estan = reparto.paradas.values_list('cliente_id', flat=True)
    return (ClienteProveedor.objects
            .filter(empresa_id=empresa_id, tipo_entidad=1, saldo__gt=0)
            .exclude(codigo_id__in=list(ya_estan))
            .order_by('razon_social')[:200])

class HojaDeRutaView(LoginRequiredMixin, View):
    """Documento que lleva el repartidor: ordenado alfabéticamente por cliente."""

    def get(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        return render(request, 'distribucion/impresion/hoja_de_ruta.html', {
            'reparto': reparto,
            'paradas': hoja_de_ruta(reparto),
            'totales': totales_hoja_de_ruta(reparto),
            'empresa': reparto.empresa,
        })


class ConsolidadoView(LoginRequiredMixin, View):
    """Control del depósito: qué se carga al vehículo, en unidades y kilos."""

    def get(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        filas, totales = consolidado(reparto)
        return render(request, 'distribucion/impresion/consolidado.html', {
            'reparto': reparto,
            'filas': filas,
            'totales': totales,
            'empresa': reparto.empresa,
        })


class EntregaView(LoginRequiredMixin, View):
    """Rendición de la entrega: qué se entregó y qué volvió (Plan 074 §7.10).

    Es lo que se carga a la vuelta del camión, leyendo la Hoja de Ruta que el repartidor
    trae marcada.
    """

    def get(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        # No hay entrega que rendir mientras el camión no salió: los saldos y el cobro
        # mínimo de cada parada recién se congelan al cerrar el reparto.
        if reparto.editable:
            messages.warning(request, "El reparto todavía está armado: cerralo antes de rendir la entrega.")
            return redirect('distribucion_reparto_detalle', reparto_id=reparto.id)
        return render(request, 'distribucion/entrega.html', {
            'reparto': reparto,
            'paradas': hoja_de_ruta(reparto),
            'por_recibir': paradas_por_recibir(reparto),
            'conciliacion': conciliacion(reparto),
        })

    def post(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        if reparto.editable:
            messages.warning(request, "El reparto todavía está armado: cerralo antes de rendir la entrega.")
            return redirect('distribucion_reparto_detalle', reparto_id=reparto.id)

        parada = get_object_or_404(
            RepartoParada, id=request.POST.get('parada'), reparto=reparto)
        accion = request.POST.get('accion')

        try:
            if accion == 'entregada':
                marcar_entregada(parada, request.user)
                messages.success(request, f"{parada.venta.cliente_razon_social}: entregada.")
            elif accion == 'no_entregada':
                marcar_no_entregada(parada, request.POST.get('observacion'))
                messages.warning(
                    request,
                    f"{parada.venta.cliente_razon_social}: marcada como NO entregada. "
                    "Registrá la Recepción de Devoluciones cuando vuelva la mercadería.")
        except ValueError as error:
            messages.error(request, str(error))

        return redirect('distribucion_entrega', reparto_id=reparto.id)


class RecepcionDevolucionView(LoginRequiredMixin, View):
    """Conteo de lo que volvió al depósito, y emisión de la NC desde ahí."""

    def get(self, request, parada_id):
        empresa_id = request.session.get('empresa_id')
        parada = get_object_or_404(
            RepartoParada, id=parada_id, reparto__empresa_id=empresa_id)
        recepcion = crear_recepcion(parada, request.user)

        # El renglón se arma acá y no en el template: Django no tiene lookup de
        # diccionario por clave, y agregar un filtro sólo para esto sería peor.
        devueltos = {i.venta_item_id: i for i in recepcion.items.select_related('motivo')}
        filas = [{'item': item, 'dev': devueltos.get(item.id)}
                 for item in parada.venta.items.select_related('producto')]

        return render(request, 'distribucion/recepcion_devolucion.html', {
            'parada': parada,
            'recepcion': recepcion,
            'filas': filas,
            'motivos': MotivoDevolucion.objects.filter(
                empresa_id=empresa_id, activo=True).exclude(momento='PRE_CARGA'),
        })

    def post(self, request, parada_id):
        empresa_id = request.session.get('empresa_id')
        parada = get_object_or_404(
            RepartoParada, id=parada_id, reparto__empresa_id=empresa_id)
        recepcion = crear_recepcion(parada, request.user)
        accion = request.POST.get('accion')

        try:
            if accion == 'guardar':
                cantidades, motivos, observaciones = {}, {}, {}
                for clave, valor in request.POST.items():
                    if clave.startswith('cantidad_'):
                        item_id = clave.replace('cantidad_', '')
                        cantidades[item_id] = (valor or '0').replace('.', '').replace(',', '.')
                    elif clave.startswith('motivo_'):
                        motivos[clave.replace('motivo_', '')] = valor
                    elif clave.startswith('obs_'):
                        observaciones[clave.replace('obs_', '')] = valor
                cargar_items(recepcion, cantidades, motivos, observaciones)
                messages.success(request, "Conteo guardado.")

            elif accion == 'confirmar':
                confirmar_recepcion(recepcion, request.user)
                messages.success(
                    request,
                    f"Recepción {recepcion.numero_formateado} confirmada. "
                    "Ya podés emitir la Nota de Crédito.")

            elif accion == 'emitir_nc':
                nota = emitir_nota_credito(
                    recepcion, request.user,
                    observacion=request.POST.get('observacion') or None)
                messages.success(
                    request,
                    f"Nota de Crédito {nota.tipo.detalle} "
                    f"{nota.punto:04d}-{nota.numero:08d} emitida por $ {nota.total}.")
                return redirect('distribucion_entrega', reparto_id=parada.reparto_id)

        except (ValueError, Exception) as error:
            messages.error(request, str(error))

        return redirect('distribucion_recepcion', parada_id=parada.id)


class CobranzaRepartoView(LoginRequiredMixin, View):
    """Carga de la cobranza que trae el repartidor (Plan 074 7.7).

    El usuario carga UN importe por medio de pago; el corte por `condic` y la imputacion
    FIFO los hace el sistema. La previsualizacion muestra el resultado ANTES de grabar,
    para que quien carga vea a que comprobantes va a parar cada peso.
    """

    def get(self, request, reparto_id):
        empresa_id = request.session.get('empresa_id')
        reparto = get_object_or_404(Reparto, id=reparto_id, empresa_id=empresa_id)
        return render(request, 'distribucion/cobranza.html',
                      self._contexto(request, reparto, request.GET.get('parada')))

    def post(self, request, reparto_id):
        empresa_id = request.session.get('empresa_id')
        reparto = get_object_or_404(Reparto, id=reparto_id, empresa_id=empresa_id)
        parada = get_object_or_404(
            RepartoParada, id=request.POST.get('parada'), reparto=reparto)
        cliente = parada.venta.cliente
        valores = _valores_del_form(request.POST)

        try:
            if request.POST.get('accion') == 'previsualizar':
                contexto = self._contexto(request, reparto, parada.id)
                contexto['plan'] = planificar_cobranza(cliente, empresa_id, valores)
                contexto['valores'] = valores
                return render(request, 'distribucion/cobranza.html', contexto)

            cobrador_id = request.POST.get('cobrador') or None
            cobrador = Personal.objects.filter(
                id=cobrador_id, empresa_id=empresa_id).first() if cobrador_id else None
            recibos = registrar_cobranza(
                reparto, cliente, valores, request.user, parada=parada,
                cobrador=cobrador,
                observaciones=request.POST.get('observaciones') or None)
            detalle = ", ".join(
                f"RC {r.punto:04d}-{r.numero:08d} (condic {r.condic})" for r in recibos)
            messages.success(request, f"Cobranza registrada: {detalle}.")
        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))

        return redirect('distribucion_cobranza', reparto_id=reparto.id)

    def _contexto(self, request, reparto, parada_id):
        empresa_id = request.session.get('empresa_id')
        parada = (reparto.paradas.filter(id=parada_id)
                  .select_related('venta__cliente').first() if parada_id else None)
        cliente = parada.venta.cliente if parada else None
        contexto = {
            'reparto': reparto,
            'parada': parada,
            'cliente': cliente,
            'paradas': hoja_de_ruta(reparto),
            'resumen': resumen_caja(reparto),
            'cobradores': Personal.objects.filter(
                empresa_id=empresa_id, activo=True, es_cobrador=True),
        }
        if cliente:
            contexto['comprobantes'] = comprobantes_abiertos(cliente, empresa_id)
            contexto['saldo_operativo'] = saldo_operativo(cliente, empresa_id)
            contexto['saldo_fiscal'] = saldo_fiscal(cliente, empresa_id)
        return contexto


def _valores_del_form(post):
    """Arma la lista de valores desde el formulario, desformateando los importes es-AR."""
    valores = []
    for clave, importe in post.items():
        if not clave.startswith('valor_'):
            continue
        limpio = (importe or '').replace('.', '').replace(',', '.')
        try:
            monto = Decimal(limpio or '0')
        except (InvalidOperation, ValueError):
            monto = Decimal('0')
        if monto <= 0:
            continue
        valores.append({'categoria': clave.replace('valor_', '').upper(),
                        'importe': monto})
    return valores


class RendicionRepartoView(LoginRequiredMixin, View):
    """Cuadro esperado vs. cobrado vs. rendido, y declaracion a Tesoreria (7.9)."""

    def get(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        return render(request, 'distribucion/rendicion.html', {
            'reparto': reparto,
            'resumen': resumen_caja(reparto),
        })

    def post(self, request, reparto_id):
        reparto = get_object_or_404(
            Reparto, id=reparto_id, empresa_id=request.session.get('empresa_id'))
        importe = (request.POST.get('efectivo_pesos') or '0').replace('.', '').replace(',', '.')
        try:
            rendir_reparto(reparto, request.user,
                           efectivo_pesos=Decimal(importe or '0'),
                           observaciones=request.POST.get('observaciones') or None)
            messages.success(
                request,
                "Rendicion declarada. Queda EN TRANSITO hasta que el tesorero la cuente "
                "y la acepte desde la recepcion de rendiciones de Tesoreria.")
        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))
        return redirect('distribucion_rendicion', reparto_id=reparto.id)


class SaldosClientesView(LoginRequiredMixin, View):
    """Clientes a cobrar, agrupado por vendedor (Plan 074 7.8)."""

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        condics = request.GET.getlist('condic') or ['1', '2']
        datos = listado_saldos(
            empresa_id,
            vendedor_id=request.GET.get('vendedor') or None,
            zona_id=request.GET.get('zona') or None,
            dia_visita=request.GET.get('dia') or None,
            condics=[int(c) for c in condics])
        return render(request, 'distribucion/saldos_clientes.html', {
            'datos': datos,
            'vendedores': Personal.objects.filter(
                empresa_id=empresa_id, activo=True, es_vendedor=True),
            'zonas': ZonaReparto.objects.filter(empresa_id=empresa_id, activa=True),
            'dias': DiaVisita.DIAS,
            'filtros': {
                'vendedor': request.GET.get('vendedor') or '',
                'zona': request.GET.get('zona') or '',
                'dia': request.GET.get('dia') or '',
                'condics': condics,
            },
        })


class RecepcionRendicionesView(LoginRequiredMixin, View):
    """Bandeja de la TESORERÍA DE REPARTO: contar lo que cada repartidor trajo (Plan 076 §B).

    Es el paso 2 de la rendición, y el motivo por el que existe el nivel intermedio: quien
    recibe a los repartidores no es el tesorero central, sino un administrativo que cuenta
    lo que cada uno trae, lo retiene, y después entrega el consolidado a Tesorería.

    EL QUE DECLARA NO ES EL MISMO QUE CUENTA: la diferencia queda registrada con su asiento,
    no absorbida en silencio.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        return render(request, 'distribucion/recepcion_rendiciones.html', {
            'rendiciones': rendiciones_por_recibir(empresa_id, sucursal_id),
            'caja': tesoreria_reparto(empresa_id, sucursal_id),
        })

    def post(self, request):
        from verticalidades.distribucion.models import RendicionReparto

        empresa_id = request.session.get('empresa_id')
        vinculo = get_object_or_404(
            RendicionReparto, id=request.POST.get('rendicion'),
            reparto__empresa_id=empresa_id)
        contado = (request.POST.get('contado_pesos') or '0').replace('.', '').replace(',', '.')

        try:
            retiro = recibir_rendicion(vinculo.retiro, request.user,
                                       contado_pesos=Decimal(contado or '0'))
            if retiro.diferencia_pesos:
                messages.warning(
                    request,
                    f"Rendición del reparto {vinculo.reparto.numero} recibida con una "
                    f"diferencia de $ {retiro.diferencia_pesos}. Quedó su asiento.")
            else:
                messages.success(
                    request,
                    f"Rendición del reparto {vinculo.reparto.numero} recibida sin diferencias.")
        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))

        return redirect('distribucion_recepcion_rendiciones')


class CobranzaVendedorView(LoginRequiredMixin, View):
    """Cobranza y rendición de un VENDEDOR, fuera de todo reparto (Plan 076 §C).

    El vendedor le cobra al cliente que viene esquivando el pago y al que le hace la
    guardia. No tiene hoja de ruta ni paradas: sólo plata que entra y que después entrega
    a la Tesorería de Reparto.

    PARA PODER RENDIR HAY QUE HABER RETENIDO: lo que cobra cae en una sesión recaudadora
    abierta a su nombre, y esa sesión se cierra recién cuando rinde.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        vendedor = self._vendedor(request, empresa_id)
        contexto = {
            'vendedores': Personal.objects.filter(
                empresa_id=empresa_id, activo=True).filter(
                    Q(es_vendedor=True) | Q(es_cobrador=True)),
            'vendedor': vendedor,
            'cliente': None,
        }
        if vendedor:
            contexto['resumen'] = resumen_vendedor(vendedor)
            contexto['sesion'] = sesion_abierta_del_vendedor(
                vendedor, request.session.get('sucursal_id'))

        cliente_id = request.GET.get('cliente')
        if cliente_id:
            cliente = ClienteProveedor.objects.filter(
                codigo_id=cliente_id, empresa_id=empresa_id).first()
            if cliente:
                contexto['cliente'] = cliente
                contexto['comprobantes'] = comprobantes_abiertos(cliente, empresa_id)
                contexto['saldo_operativo'] = saldo_operativo(cliente, empresa_id)
                contexto['saldo_fiscal'] = saldo_fiscal(cliente, empresa_id)
        return render(request, 'distribucion/cobranza_vendedor.html', contexto)

    def post(self, request):
        empresa_id = request.session.get('empresa_id')
        sucursal_id = request.session.get('sucursal_id')
        vendedor = self._vendedor(request, empresa_id)
        accion = request.POST.get('accion')

        try:
            if not vendedor:
                raise ValueError("Elegí el vendedor que trajo la plata.")

            if accion == 'rendir':
                importe = (request.POST.get('efectivo_pesos') or '0').replace('.', '').replace(',', '.')
                rendir_vendedor(vendedor, request.user,
                                efectivo_pesos=Decimal(importe or '0'),
                                sucursal_id=sucursal_id,
                                observaciones=request.POST.get('observaciones') or None)
                messages.success(
                    request,
                    "Rendición declarada. Queda EN TRÁNSITO hasta que la Tesorería de "
                    "Reparto la cuente y la acepte.")
            else:
                cliente = get_object_or_404(
                    ClienteProveedor, codigo_id=request.POST.get('cliente'),
                    empresa_id=empresa_id)
                recibos = registrar_cobranza(
                    None, cliente, _valores_del_form(request.POST), request.user,
                    cobrador=vendedor, sucursal_id=sucursal_id,
                    observaciones=request.POST.get('observaciones') or None)
                detalle = ", ".join(
                    f"RC {r.punto:04d}-{r.numero:08d}" for r in recibos)
                messages.success(request, f"Cobranza registrada: {detalle}.")
        except (ValueError, InvalidOperation) as error:
            messages.error(request, str(error))

        destino = reverse('distribucion_cobranza_vendedor')
        if vendedor:
            destino = f"{destino}?vendedor={vendedor.id}"
        return redirect(destino)

    def _vendedor(self, request, empresa_id):
        vendedor_id = request.GET.get('vendedor') or request.POST.get('vendedor')
        if not vendedor_id:
            return None
        return Personal.objects.filter(id=vendedor_id, empresa_id=empresa_id).first()


class DevolucionesReporteView(LoginRequiredMixin, View):
    """Reporte de devoluciones (Plan 074 §7.10).

    La pregunta que responde no es CUÁNTO sino POR QUÉ: un total no cambia ninguna conducta,
    pero ver que el 60 % son «negocio cerrado», o que se concentran en un repartidor o en un
    producto que llega roto, sí. Por eso son cortes sobre los mismos renglones.
    """

    def get(self, request):
        empresa_id = request.session.get('empresa_id')
        filtros = {
            'desde': request.GET.get('desde') or None,
            'hasta': request.GET.get('hasta') or None,
            'motivo': request.GET.get('motivo') or '',
            'repartidor': request.GET.get('repartidor') or '',
            'cliente': request.GET.get('cliente') or '',
            'solo_no_apto': request.GET.get('solo_no_apto') == '1',
        }
        datos = reporte_devoluciones(
            empresa_id,
            desde=filtros['desde'], hasta=filtros['hasta'],
            motivo_id=filtros['motivo'] or None,
            repartidor_id=filtros['repartidor'] or None,
            cliente_id=filtros['cliente'] or None,
            solo_no_apto=filtros['solo_no_apto'])

        return render(request, 'distribucion/reporte_devoluciones.html', {
            'datos': datos,
            'filtros': filtros,
            'motivos': MotivoDevolucion.objects.filter(empresa_id=empresa_id, activo=True),
            'repartidores': Personal.objects.filter(
                empresa_id=empresa_id, activo=True, es_repartidor=True),
        })


class CorrelativosDistribucionView(LoginRequiredMixin, View):
    """Integridad de las series que emite el módulo (Plan 074 §4.2).

    El control de integridad SÓLO es posible sobre los comprobantes que uno EMITE con
    numeración propia: sobre el número de un tercero no se puede auditar nada. Acá se ven
    las cinco series de Distribución —Pedido, Reparto, Recepción de Devoluciones, PRE y
    NCI— con sus huecos, duplicados y el desfasaje contra el contador.
    """

    SERIES = ('PEDIDO', 'REPARTO', 'RECEPCION_DEVOLUCION', 'VENTA_PRE', 'VENTA_NCI')

    def get(self, request):
        from core.services.numeracion import auditar_correlativos

        empresa_id = request.session.get('empresa_id')
        if not empresa_id:
            return redirect('seleccion_empresa')

        filas = [f for f in auditar_correlativos(empresa_id=empresa_id)
                 if f['tipo'] in self.SERIES]
        return render(request, 'distribucion/correlativos.html', {
            'filas': filas,
            'con_problemas': [f for f in filas if not f['ok']],
        })
