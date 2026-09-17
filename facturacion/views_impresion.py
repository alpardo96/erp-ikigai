from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from .services.pdf_service import generar_pdf_venta
import logging

logger = logging.getLogger(__name__)

@login_required
def imprimir_factura(request, venta_id):
    """
    Vista que devuelve el PDF generado para una venta, 
    utilizando la plantilla de fondo y dibujando los datos.
    """
    try:
        pdf_bytes = generar_pdf_venta(venta_id)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        # Para que se muestre en el navegador en vez de descargar forzosamente (inline vs attachment)
        response['Content-Disposition'] = f'inline; filename="Factura_{venta_id}.pdf"'
        return response
    except Exception as e:
        logger.exception("Error al generar PDF de la factura")
        return HttpResponse(f"Error al generar el comprobante PDF: {str(e)}", status=500)

@login_required
def imprimir_preventa(request, preventa_id):
    """
    Vista que devuelve el PDF generado para una preventa/reserva.
    """
    try:
        from .services.pdf_service import generar_pdf_preventa
        pdf_bytes = generar_pdf_preventa(preventa_id)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Reserva_Preventa_{preventa_id}.pdf"'
        return response
    except Exception as e:
        logger.exception("Error al generar PDF de la preventa")
        return HttpResponse(f"Error al generar el comprobante PDF: {str(e)}", status=500)
