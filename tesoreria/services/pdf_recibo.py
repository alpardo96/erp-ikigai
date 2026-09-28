import io
import os
import logging
from decimal import Decimal
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from tesoreria.models import Recibo, MovimientoCajaDetalle, TransaccionBancaria, ValorTerceros
from core.utils.numeros_a_letras import numero_a_letras

logger = logging.getLogger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = A4  # 595.27, 841.89

def format_arg(val, decimals=2):
    """Formatea un número en formato argentino (miles con punto, decimales con coma)."""
    if val is None:
        val = Decimal('0.00')
    elif isinstance(val, (int, float, str)):
        val = Decimal(str(val))
    s = f"{val:,.{decimals}f}"
    return s.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')

class PDFBuilder:
    def __init__(self, buffer):
        self.c = canvas.Canvas(buffer, pagesize=A4)
        self.c.setLineWidth(0.5)

    def draw_line(self, x1, y1, x2, y2):
        self.c.line(x1, PAGE_HEIGHT - y1, x2, PAGE_HEIGHT - y2)

    def draw_rect(self, x, y, width, height, fill=0):
        self.c.rect(x, PAGE_HEIGHT - y - height, width, height, stroke=1, fill=fill)

    def draw_text(self, text, x, y, font_name="Helvetica", font_size=9, align="left"):
        self.c.setFont(font_name, font_size)
        y_rl = PAGE_HEIGHT - y
        if align == "left":
            self.c.drawString(x, y_rl, str(text))
        elif align == "right":
            self.c.drawRightString(x, y_rl, str(text))
        elif align == "center":
            self.c.drawCentredString(x, y_rl, str(text))

    def draw_image(self, img_path, x, y, width, height):
        try:
            from reportlab.lib.utils import ImageReader
            self.c.drawImage(
                ImageReader(img_path), x, PAGE_HEIGHT - y - height,
                width=width, height=height, preserveAspectRatio=True, mask='auto'
            )
        except Exception as e:
            logger.warning(f"Error drawing image {img_path}: {e}")

    def save(self):
        self.c.save()


def generar_pdf_recibo(recibo_id):
    """
    Genera el comprobante oficial de Recibo de Cobranza dibujando con ReportLab nativo,
    utilizando el mismo motor exacto de renderizado y escalado proporcional de logo que en Facturación.
    """
    recibo = Recibo.objects.select_related(
        'cliente', 'empresa', 'sucursal', 'cliente__jurisdiccion'
    ).get(pk=recibo_id)

    empresa = recibo.empresa
    cliente = recibo.cliente

    packet = io.BytesIO()
    builder = PDFBuilder(packet)

    # === SKELETON (MARCOS Y LÍNEAS) ===
    # Marco exterior
    builder.draw_rect(15, 15, 565, 785)

    # Línea superior
    builder.draw_line(15, 45, 580, 45)

    # Recuadro central de Letra 'X' (Recibo)
    builder.draw_rect(270, 45, 55, 45)
    builder.draw_text("X", 297.5, 75, font_name="Helvetica-Bold", font_size=28, align="center")
    builder.draw_text("RECIBO", 297.5, 87, font_name="Helvetica-Bold", font_size=7, align="center")

    # Separador vertical central entre emisor y datos comprobante
    builder.draw_line(297.5, 90, 297.5, 170)

    # Línea horizontal divisoria de cabecera
    builder.draw_line(15, 170, 580, 170)

    # === CABECERA: EMISOR (Izquierda) ===
    if recibo.condic == 1:
        if empresa.logo:
            # Mismo código exacto que en Facturación de Ventas con preserveAspectRatio=True
            builder.draw_image(empresa.logo, 122, 55, 80, 45)

        nombre_emisor = empresa.nombre.upper()
        direccion_emisor = (recibo.sucursal.direccion or empresa.direccion or '').upper()

        tels = []
        if empresa.telefono:
            import re
            for p in re.split(r'[,|/]+', empresa.telefono):
                p_clean = p.strip()
                if p_clean and p_clean not in tels:
                    tels.append(p_clean)
        if recibo.sucursal and recibo.sucursal.telefono:
            suc_tel = recibo.sucursal.telefono.strip()
            if suc_tel and suc_tel not in tels:
                tels.append(suc_tel)

        telefono_emisor = " - ".join(tels)
        if telefono_emisor:
            telefono_emisor = f"TEL: {telefono_emisor}"
        email_emisor = empresa.correo or ""
        iva_emisor = (empresa.condicion_iva or "RESPONSABLE INSCRIPTO").upper()

        y_emisor = 115
        builder.draw_text(nombre_emisor, 162.5, y_emisor, font_name="Helvetica-Bold", font_size=10, align="center")
        builder.draw_text(direccion_emisor, 162.5, y_emisor + 15, font_size=8, align="center")

        tel_mail = telefono_emisor
        if email_emisor:
            tel_mail += f" / Email: {email_emisor}" if tel_mail else f"Email: {email_emisor}"
        if tel_mail:
            builder.draw_text(tel_mail, 162.5, y_emisor + 30, font_size=8, align="center")

        builder.draw_text(f"IVA: {iva_emisor}", 162.5, y_emisor + 45, font_name="Helvetica-Bold", font_size=9, align="center")
    else:
        builder.draw_text("DOCUMENTO NO VÁLIDO COMO FACTURA", 162.5, 100, font_name="Helvetica-Bold", font_size=10, align="center")

    # === CABECERA: COMPROBANTE (Derecha) ===
    builder.draw_text("RECIBO DE COBRANZA", 431.25, 65, font_name="Helvetica-Bold", font_size=15, align="center")

    builder.draw_text("Punto:", 330, 95, font_name="Helvetica-Bold", font_size=10)
    builder.draw_text(f"{recibo.punto:05d}", 370, 95, font_size=10)

    builder.draw_text("Comp. Nro:", 420, 95, font_name="Helvetica-Bold", font_size=10)
    builder.draw_text(f"{recibo.numero:08d}", 485, 95, font_size=10)

    builder.draw_text("Fecha de Emisión:", 330, 115, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(recibo.fecha.strftime('%d/%m/%Y'), 430, 115, font_size=9)

    if recibo.condic == 1:
        builder.draw_text("CUIT:", 330, 130, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(empresa.cuit, 370, 130, font_size=9)

        builder.draw_text("Ingresos Brutos:", 330, 145, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(empresa.cuit, 420, 145, font_size=9)

        builder.draw_text("Inicio Actividades:", 330, 160, font_name="Helvetica-Bold", font_size=9)
        inicio_emisor = empresa.fecha_inicio_actividades.strftime('%d/%m/%Y') if empresa.fecha_inicio_actividades else "01/01/2000"
        builder.draw_text(inicio_emisor, 430, 160, font_size=9)

    if recibo.anulado:
        builder.draw_rect(340, 20, 180, 20)
        builder.draw_text("ANULADO", 430, 35, font_name="Helvetica-Bold", font_size=14, align="center")

    # === DATOS DEL CLIENTE ===
    builder.draw_line(15, 235, 580, 235)

    dom_cli = getattr(cliente, 'domicilio', '') or ''
    loc_cli = getattr(cliente, 'localidad', '') or ''
    cuit_cli = getattr(cliente, 'cuit', '') or ''
    iva_cli = getattr(cliente, 'condicion_iva', '') or 'CONSUMIDOR FINAL'

    builder.draw_text("Recibimos de:", 25, 188, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(cliente.razon_social.upper() if cliente else "CLIENTE OCASIONAL", 110, 188, font_name="Helvetica-Bold", font_size=9)

    builder.draw_text("CUIT:", 400, 188, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(cuit_cli or "—", 435, 188, font_size=9)

    builder.draw_text("Domicilio:", 25, 205, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(f"{dom_cli} - {loc_cli}".strip(" -").upper() or "—", 85, 205, font_size=9)

    builder.draw_text("Condición IVA:", 25, 222, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(iva_cli.upper(), 110, 222, font_size=9)

    # === IMPORTE EN LETRAS ===
    builder.draw_line(15, 270, 580, 270)
    builder.draw_text("La suma de:", 25, 250, font_name="Helvetica-Bold", font_size=9)
    total_letras = numero_a_letras(recibo.total)
    builder.draw_text(f"$ {format_arg(recibo.total)} ({total_letras})", 95, 250, font_name="Helvetica-Bold", font_size=9.5)

    if recibo.observaciones:
        builder.draw_text(f"Observaciones: {recibo.observaciones}", 25, 264, font_size=8)

    # === GRILLAS DINÁMICAS ===
    y_cursor = 285

    # 1. Comprobantes cancelados / imputados
    aplicaciones = list(recibo.aplicaciones.select_related('venta__tipo').all())
    if aplicaciones:
        builder.draw_rect(15, y_cursor, 565, 18, fill=0)
        builder.draw_text("COMPROBANTES CANCELADOS / IMPUTADOS", 20, y_cursor + 13, font_name="Helvetica-Bold", font_size=8.5)
        y_cursor += 18

        # Encabezado tabla
        builder.draw_line(15, y_cursor + 14, 580, y_cursor + 14)
        builder.draw_text("Fecha", 25, y_cursor + 10, font_name="Helvetica-Bold", font_size=8)
        builder.draw_text("Comprobante", 100, y_cursor + 10, font_name="Helvetica-Bold", font_size=8)
        builder.draw_text("Total Comp.", 380, y_cursor + 10, font_name="Helvetica-Bold", font_size=8, align="right")
        builder.draw_text("Importe Aplicado", 540, y_cursor + 10, font_name="Helvetica-Bold", font_size=8, align="right")
        y_cursor += 16

        for ap in aplicaciones:
            fec = ap.venta.fecha.strftime('%d/%m/%Y') if ap.venta else "—"
            tipo_desc = ap.venta.tipo.detalle if (ap.venta and ap.venta.tipo) else "Comprobante"
            nro_comp = f"{ap.venta.punto:05d}-{ap.venta.numero:08d}" if ap.venta else "—"
            tot_v = f"$ {format_arg(ap.venta.total)}" if ap.venta else "—"
            imp_ap = f"$ {format_arg(ap.importe_pesos)}"

            builder.draw_text(fec, 25, y_cursor + 10, font_size=8)
            builder.draw_text(f"{tipo_desc} {nro_comp}", 100, y_cursor + 10, font_size=8)
            builder.draw_text(tot_v, 380, y_cursor + 10, font_size=8, align="right")
            builder.draw_text(imp_ap, 540, y_cursor + 10, font_name="Helvetica-Bold", font_size=8, align="right")
            y_cursor += 13
            if y_cursor > 650:
                break
        y_cursor += 6

    # 2. Detalle de valores / Medios de cobro
    detalles = list(MovimientoCajaDetalle.objects.filter(movimiento_caja__recibo=recibo).select_related('medio_pago'))
    if detalles:
        builder.draw_rect(15, y_cursor, 565, 18, fill=0)
        builder.draw_text("DETALLE DE MEDIOS DE COBRO RECIBIDOS", 20, y_cursor + 13, font_name="Helvetica-Bold", font_size=8.5)
        y_cursor += 18

        builder.draw_line(15, y_cursor + 14, 580, y_cursor + 14)
        builder.draw_text("Medio de Pago", 25, y_cursor + 10, font_name="Helvetica-Bold", font_size=8)
        builder.draw_text("Detalle / Moneda Extranjera", 200, y_cursor + 10, font_name="Helvetica-Bold", font_size=8)
        builder.draw_text("Importe ($)", 540, y_cursor + 10, font_name="Helvetica-Bold", font_size=8, align="right")
        y_cursor += 16

        for d in detalles:
            medio_nom = d.medio_pago.nombre if d.medio_pago else "Medio de Pago"
            det_extra = ""
            if d.importe_moneda_extranjera and d.importe_moneda_extranjera > 0:
                det_extra = f"U$D {format_arg(d.importe_moneda_extranjera)} @ Cotiz. {format_arg(d.cotizacion)}"

            builder.draw_text(medio_nom, 25, y_cursor + 10, font_size=8.5)
            builder.draw_text(det_extra, 200, y_cursor + 10, font_size=8)
            builder.draw_text(f"$ {format_arg(d.importe)}", 540, y_cursor + 10, font_name="Helvetica-Bold", font_size=8.5, align="right")
            y_cursor += 13

        # Total
        builder.draw_line(350, y_cursor + 4, 565, y_cursor + 4)
        builder.draw_text("TOTAL RECIBO:", 420, y_cursor + 16, font_name="Helvetica-Bold", font_size=10, align="right")
        builder.draw_text(f"$ {format_arg(recibo.total)}", 540, y_cursor + 16, font_name="Helvetica-Bold", font_size=11, align="right")
        y_cursor += 24

    # === PIE DE PÁGINA: FIRMAS Y DATOS DE CONTROL ===
    builder.draw_line(15, 710, 580, 710)

    # Recuadro de Firma
    builder.draw_line(360, 765, 520, 765)
    builder.draw_text("Firma y Aclaración", 440, 777, font_name="Helvetica-Bold", font_size=8.5, align="center")

    # Datos de control
    asiento_str = f"Asiento Contable Nro: {recibo.asiento_id}" if recibo.asiento_id else "Asiento Contable: Pendiente"
    builder.draw_text(asiento_str, 25, 760, font_size=8)
    from django.utils import timezone
    builder.draw_text(f"Impreso el {timezone.localtime().strftime('%d/%m/%Y %H:%M')}", 25, 775, font_size=7.5)

    builder.save()
    packet.seek(0)
    return packet.getvalue()
