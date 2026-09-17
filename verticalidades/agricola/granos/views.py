"""
Vistas para la verticalidad Agrícola -> Granos:
1. Configuración de Mapeos (GranoMapeo y GastoMapeo).
2. Importador de Liquidaciones Primarias de Granos (LPG) con Drag & Drop,
   previsualización AJAX, resolución al vuelo de conceptos nuevos y confirmación atómica.
"""
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from core.utils import get_empresa_activa
from contable.models import Cuenta, ParametrosContables
from productos.models import Producto
from facturacion.models import ClienteProveedor
from verticalidades.agricola.granos.models import GranoMapeo, GastoMapeo
from verticalidades.agricola.granos.services.lpg_parser import LpgPdfParser
from verticalidades.agricola.granos.services.lpg_matcher import LpgMatcher
from verticalidades.agricola.granos.services.lpg_persister import LpgPersister


@login_required
def mapeos_config_view(request):
    """
    Vista de configuración y administración de mapeos para la verticalidad Granos.
    Permite parametrizar el nomenclador de cultivos ARCA y los patrones de gastos.
    """
    empresa = get_empresa_activa(request)
    if not empresa:
        messages.error(request, "No hay una empresa activa seleccionada.")
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # 1. Guardar o Editar GranoMapeo
        if action == 'guardar_grano':
            grano_id = request.POST.get('grano_id')
            codigo_arca = request.POST.get('codigo_arca')
            descripcion_arca = request.POST.get('descripcion_arca')
            producto_id = request.POST.get('producto_id')
            cta_ventas_id = request.POST.get('cta_ventas_id')

            producto = get_object_or_404(Producto, id=producto_id, empresa=empresa)
            cta_ventas = get_object_or_404(Cuenta, id=cta_ventas_id, empresa=empresa)

            if grano_id:
                gm = get_object_or_404(GranoMapeo, id=grano_id, empresa=empresa)
                gm.codigo_arca = int(codigo_arca)
                gm.descripcion_arca = descripcion_arca
                gm.producto = producto
                gm.cta_ventas = cta_ventas
                gm.save()
                messages.success(request, f"Mapeo del grano {gm.descripcion_arca} actualizado correctamente.")
            else:
                GranoMapeo.objects.create(
                    empresa=empresa,
                    codigo_arca=int(codigo_arca),
                    descripcion_arca=descripcion_arca,
                    producto=producto,
                    cta_ventas=cta_ventas
                )
                messages.success(request, f"Mapeo de grano [{codigo_arca}] guardado exitosamente.")
            return redirect('agricola_granos_mapeos')

        # 2. Eliminar GranoMapeo
        elif action == 'eliminar_grano':
            grano_id = request.POST.get('grano_id')
            gm = get_object_or_404(GranoMapeo, id=grano_id, empresa=empresa)
            gm.delete()
            messages.success(request, "Mapeo de grano eliminado.")
            return redirect('agricola_granos_mapeos')

        # 3. Guardar o Editar GastoMapeo
        elif action == 'guardar_gasto':
            gasto_id = request.POST.get('gasto_id')
            patron = request.POST.get('patron')
            descripcion = request.POST.get('descripcion')
            cta_gasto_id = request.POST.get('cta_gasto_id')
            alicuota_sugerida = request.POST.get('alicuota_sugerida') or '10.50'

            cta_gasto = get_object_or_404(Cuenta, id=cta_gasto_id, empresa=empresa)

            if gasto_id:
                gasto = get_object_or_404(GastoMapeo, id=gasto_id, empresa=empresa)
                gasto.patron = patron
                gasto.descripcion = descripcion
                gasto.cta_gasto = cta_gasto
                gasto.alicuota_sugerida = Decimal(str(alicuota_sugerida))
                gasto.save()
                messages.success(request, f"Regla de gasto '{gasto.descripcion}' actualizada.")
            else:
                GastoMapeo.objects.create(
                    empresa=empresa,
                    patron=patron,
                    descripcion=descripcion,
                    cta_gasto=cta_gasto,
                    alicuota_sugerida=Decimal(str(alicuota_sugerida))
                )
                messages.success(request, f"Regla de gasto '{descripcion}' creada exitosamente.")
            return redirect('agricola_granos_mapeos')

        # 4. Eliminar GastoMapeo
        elif action == 'eliminar_gasto':
            gasto_id = request.POST.get('gasto_id')
            gasto = get_object_or_404(GastoMapeo, id=gasto_id, empresa=empresa)
            gasto.delete()
            messages.success(request, "Regla de gasto eliminada.")
            return redirect('agricola_granos_mapeos')

        # 5. Precargar Semilla de Gastos Iniciales
        elif action == 'precargar_semilla':
            cls_precargar_semilla(empresa)
            messages.success(request, "Se han precargado los conceptos base de gastos (Flete, Comisión, Sellado, etc.).")
            return redirect('agricola_granos_mapeos')

    granos_mapeos = GranoMapeo.objects.filter(empresa=empresa).select_related('producto', 'cta_ventas')
    gastos_mapeos = GastoMapeo.objects.filter(empresa=empresa).select_related('cta_gasto')
    
    productos = Producto.objects.filter(empresa=empresa).order_by('detalle')
    cuentas = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
    params_contables = ParametrosContables.objects.filter(empresa=empresa).first()

    context = {
        'empresa': empresa,
        'granos_mapeos': granos_mapeos,
        'gastos_mapeos': gastos_mapeos,
        'productos': productos,
        'cuentas': cuentas,
        'params_contables': params_contables
    }
    return render(request, 'agricola/granos/mapeos_config.html', context)


def cls_precargar_semilla(empresa):
    """Inicializa los conceptos y patrones estándar descubiertos en los comprobantes de muestra."""
    cta_default = Cuenta.objects.filter(empresa=empresa, imputable=1, tipo='R').first() or Cuenta.objects.filter(empresa=empresa, imputable=1).first()
    if not cta_default:
        return

    semilla = [
        ('FLETE', 'Fletes de Granos', Decimal('10.50')),
        ('COMISION', 'Comisiones de Acopio / Corretaje', Decimal('10.50')),
        ('SELLADO', 'Impuesto de Sellos / Tasas Provinciales', Decimal('0.00')),
        ('MERCADERIA EN FINAL', 'Ajustes de Calidad / Descuentos en Final', Decimal('0.00')),
        ('SECADO', 'Gastos de Secado de Granos', Decimal('21.00')),
        ('ACONDICIONAMIENTO', 'Acondicionamiento y Zarandeo', Decimal('21.00')),
        ('PARITARIA', 'Gastos Paritarias y Administrativos', Decimal('21.00')),
    ]
    for patron, desc, alic in semilla:
        GastoMapeo.objects.get_or_create(
            empresa=empresa,
            patron=patron,
            defaults={
                'descripcion': desc,
                'cta_gasto': cta_default,
                'alicuota_sugerida': alic
            }
        )


@login_required
def importar_lpg_view(request):
    """
    Vista del importador de Liquidaciones Primarias de Granos (LPG).
    Gestiona el formulario Drag & Drop y endpoints AJAX para previsualización y confirmación.
    """
    empresa = get_empresa_activa(request)
    if not empresa:
        messages.error(request, "No hay una empresa activa seleccionada.")
        return redirect('dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')

        # Endpoint AJAX 1: Previsualizar lote de PDFs
        if action == 'preview_ajax':
            archivos = request.FILES.getlist('archivos_pdf')
            if not archivos:
                return JsonResponse({'success': False, 'error': 'No se recibieron archivos PDF.'}, status=400)

            parsed_list = []
            for arch in archivos:
                try:
                    pdata = LpgPdfParser.parse_pdf(arch)
                    pdata['nombre_archivo'] = arch.name
                    parsed_list.append(pdata)
                except Exception as e:
                    parsed_list.append({
                        'nombre_archivo': arch.name,
                        'error_parseo': str(e),
                        'es_lpg': False
                    })

            # Ejecutar cotejo de mapeos
            matched_list = LpgMatcher.match_liquidaciones(empresa, [p for p in parsed_list if 'error_parseo' not in p])

            # Serializar cuentas y productos para combos de asignación rápida en frontend
            cuentas_imputables = list(Cuenta.objects.filter(empresa=empresa, imputable=1).values('id', 'jerarquia', 'cuenta', 'tipo'))
            productos_list = list(Producto.objects.filter(empresa=empresa).values('id', 'detalle', 'codigo_anterior'))

            return JsonResponse({
                'success': True,
                'liquidaciones': matched_list,
                'cuentas': cuentas_imputables,
                'productos': productos_list
            })

        # Endpoint AJAX 2: Confirmar e Importar liquidaciones seleccionadas
        elif action == 'confirm_ajax':
            try:
                payload = json.loads(request.POST.get('payload', '{}'))
                items_a_importar = payload.get('items', [])
                sucursal_id = request.session.get('sucursal_id')
                sucursal = None
                if sucursal_id:
                    from empresas.models import Sucursal
                    sucursal = Sucursal.objects.filter(id=sucursal_id, empresa=empresa).first()
                if not sucursal:
                    from empresas.models import Sucursal
                    sucursal = Sucursal.objects.filter(empresa=empresa).first()

                resultados_importacion = []
                errores = []

                for item in items_a_importar:
                    try:
                        matched_data = item['matched_data']
                        overrides = item.get('overrides', {})
                        res = LpgPersister.persistir_liquidacion(
                            empresa=empresa,
                            sucursal=sucursal,
                            usuario=request.user,
                            matched_data=matched_data,
                            overrides=overrides
                        )
                        resultados_importacion.append(res)
                    except Exception as err:
                        errores.append({
                            'coe': item.get('matched_data', {}).get('parsed', {}).get('coe'),
                            'error': str(err)
                        })

                return JsonResponse({
                    'success': True,
                    'importados': resultados_importacion,
                    'errores': errores,
                    'total_procesados': len(resultados_importacion)
                })
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)

    # Render GET
    cuentas_imputables = Cuenta.objects.filter(empresa=empresa, imputable=1).order_by('jerarquia')
    productos = Producto.objects.filter(empresa=empresa).order_by('detalle')
    params_contables = ParametrosContables.objects.filter(empresa=empresa).first()

    context = {
        'empresa': empresa,
        'cuentas': cuentas_imputables,
        'productos': productos,
        'params_contables': params_contables
    }
    return render(request, 'agricola/granos/importar_lpg.html', context)
