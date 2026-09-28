from xhtml2pdf import pisa
from django.template.loader import render_to_string
from django.http import HttpResponse
from datetime import date
from io import BytesIO

def render_pdf_response(template_name, context, filename, as_attachment=False):
    html_string = render_to_string(template_name, context)
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_string.encode("utf-8")), result)
    
    if not pdf.err:
        response = HttpResponse(result.getvalue(), content_type='application/pdf')
        disposition = 'attachment' if as_attachment else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="{filename}"'
        return response
    return HttpResponse('Error al generar PDF', status=400)

