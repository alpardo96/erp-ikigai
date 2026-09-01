from xhtml2pdf import pisa
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.utils import timezone
from io import BytesIO

def render_pdf_response(template_name, context, filename):
    """
    Renderiza un template HTML a PDF usando xhtml2pdf.
    Retorna un HttpResponse con el PDF adjunto.
    """
    html_string = render_to_string(template_name, context)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("utf-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    return HttpResponse('Error al generar PDF', status=400)

def exportar_diario_pdf(asientos, empresa, fecha_desde=None, fecha_hasta=None):
    context = {
        'asientos': asientos,
        'empresa': empresa,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'fecha_emision': timezone.localtime(),
    }
    return render_pdf_response(
        'contable/pdf/libro_diario_pdf.html',
        context,
        f'libro_diario_{timezone.localdate().strftime("%Y%m%d")}.pdf'
    )

def exportar_mayor_pdf(cuentas_data, empresa, ejercicio=None, fecha_desde=None, fecha_hasta=None):
    ej_limpio = None
    if ejercicio:
        ej_limpio = ejercicio.ejercicio.split("-")[-1].strip() if "-" in ejercicio.ejercicio else ejercicio.ejercicio
        
    context = {
        'cuentas_data': cuentas_data,
        'empresa': empresa,
        'ejercicio': ejercicio,
        'ejercicio_limpio': ej_limpio,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'fecha_emision': timezone.localtime(),
    }
    return render_pdf_response(
        'contable/pdf/libro_mayor_pdf.html',
        context,
        f'libro_mayor_{timezone.localdate().strftime("%Y%m%d")}.pdf'
    )

def exportar_balance_pdf(balance_data, empresa, fecha_hasta, context_data=None, ejercicio=None, fecha_desde=None):
    ej_limpio = None
    if ejercicio:
        ej_limpio = ejercicio.ejercicio.split("-")[-1].strip() if "-" in ejercicio.ejercicio else ejercicio.ejercicio
        
    context = {
        'balance': balance_data,
        'empresa': empresa,
        'ejercicio': ejercicio,
        'ejercicio_limpio': ej_limpio,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'fecha_emision': timezone.localtime(),
        'context_data': context_data
    }
    return render_pdf_response(
        'contable/pdf/balance_pdf.html',
        context,
        f'balance_{timezone.localdate().strftime("%Y%m%d")}.pdf'
    )
