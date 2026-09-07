import io
import os
import logging
from decimal import Decimal
from django.conf import settings
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from facturacion.models import Venta

logger = logging.getLogger(__name__)

PAGE_WIDTH, PAGE_HEIGHT = A4 # 595.27, 841.89

def format_arg(val, decimals=2):
    """Formatea un número en formato argentino (miles con punto, decimales con coma)."""
    if val is None:
        val = Decimal('0.00')
    elif isinstance(val, (int, float, str)):
        val = Decimal(str(val))
    s = f"{val:,.{decimals}f}"
    return s.replace(',', 'TEMP').replace('.', ',').replace('TEMP', '.')

def get_titulo_comprobante(codigo, detalle):
    """Devuelve el título limpio del comprobante."""
    d = (detalle or '').upper()
    if 'NOTA DE CRÉDITO' in d or 'NOTA DE CREDITO' in d or codigo in ['003', '008', '013']:
        return "NOTA DE CREDITO"
    elif 'NOTA DE DÉBITO' in d or 'NOTA DE DEBITO' in d or codigo in ['002', '007', '012']:
        return "NOTA DE DEBITO"
    elif 'PRESUPUESTO' in d or codigo == 'PRE':
        return "PRESUPUESTO"
    else:
        return "FACTURA"

def get_domicilio_completo_cliente(venta, cliente):
    """Arma el domicilio completo del cliente incluyendo CP, Localidad y Provincia."""
    dom = venta.cliente_domicilio or getattr(cliente, 'domicilio', '') or ''
    cp = getattr(cliente, 'codigo_postal', '') or ''
    loc = getattr(cliente, 'localidad', '') or ''
    prov = cliente.jurisdiccion.nombre if (cliente and getattr(cliente, 'jurisdiccion', None)) else ''
    
    parts = []
    if dom: parts.append(dom.strip())
        
    loc_cp_prov = ""
    if cp: loc_cp_prov += f"({cp}) "
    if loc: loc_cp_prov += f"{loc}"
    if prov:
        loc_cp_prov += f". {prov}" if loc else f"{prov}"
            
    if loc_cp_prov.strip():
        parts.append(loc_cp_prov.strip())
        
    return " - ".join(parts).upper()

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
            self.c.drawImage(ImageReader(img_path), x, PAGE_HEIGHT - y - height, width=width, height=height, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            logger.warning(f"Error drawing image {img_path}: {e}")

    def save(self):
        self.c.save()

def generar_pdf_venta(venta_id):
    """
    Genera un PDF de la venta dibujando el comprobante completo usando ReportLab.
    """
    venta = Venta.objects.select_related('tipo', 'cliente', 'empresa', 'sucursal', 'cliente__jurisdiccion').prefetch_related('items', 'alicuotas_iva', 'subproductos').get(ventas_id=venta_id)
    
    codigo = venta.tipo.codigo if venta.tipo else ''
    
    if codigo == 'PRE' or venta.condic == 2:
        layout_style = 'PRE'
    elif codigo in ['001', '002', '003', '051', '052', '053', 'FA', 'CA', 'DA', 'FMA']:
        layout_style = 'A'
    elif codigo in ['011', '012', '013', 'FC', 'CC', 'DC']:
        layout_style = 'C'
    else:
        layout_style = 'B'
        
    packet = io.BytesIO()
    builder = PDFBuilder(packet)
    
    empresa = venta.empresa
    cliente = venta.cliente
    
    # === SKELETON (MARCOS Y LÍNEAS) ===
    # Main border
    builder.draw_rect(15, 15, 565, 785)
    
    # Top margin line
    builder.draw_line(15, 45, 580, 45)
    
    # Horizontal line below header
    builder.draw_line(15, 170, 580, 170)
    
    if layout_style != 'PRE':
        # Letter Box
        builder.draw_rect(270, 45, 55, 45)
        # Vertical line separating left/right header
        builder.draw_line(297.5, 90, 297.5, 170)
    else:
        # For PRE, Letter Box is also there (usually 'X')
        builder.draw_rect(270, 45, 55, 45)
        builder.draw_line(297.5, 90, 297.5, 170)
        
    # Horizontal line separating client data from periods
    builder.draw_line(15, 235, 580, 235)
    
    # Horizontal line below client info (now periods)
    builder.draw_line(15, 255, 580, 255)
    
    # Horizontal line below items header
    builder.draw_line(15, 275, 580, 275)
    
    # Horizontal line above totals (footer)
    builder.draw_line(15, 700, 580, 700)

    # === HEADER DATA (EMISOR Y COMPROBANTE) ===
    # Letter
    letra = "X"
    if layout_style == 'A': letra = "A"
    elif layout_style == 'B': letra = "B"
    elif layout_style == 'C': letra = "C"
    builder.draw_text(letra, 297.5, 75, font_name="Helvetica-Bold", font_size=28, align="center")
    
    if layout_style != 'PRE':
        try:
            cod_afip_num = int(codigo)
            builder.draw_text(f"Cod.{cod_afip_num:02d}", 297.5, 87, font_name="Helvetica-Bold", font_size=8, align="center")
        except: pass

    # EMISOR (Left)
    if venta.condic == 1:
        if empresa.logo:
            builder.draw_image(empresa.logo, 122, 55, 80, 45)
            
        nombre_emisor = empresa.nombre.upper()
        direccion_emisor = (venta.sucursal.direccion or empresa.direccion or '').upper()
        
        tels = []
        if empresa.telefono:
            import re
            for p in re.split(r'[,|/]+', empresa.telefono):
                p_clean = p.strip()
                if p_clean and p_clean not in tels: tels.append(p_clean)
        if venta.sucursal and venta.sucursal.telefono:
            suc_tel = venta.sucursal.telefono.strip()
            if suc_tel and suc_tel not in tels: tels.append(suc_tel)
            
        telefono_emisor = " - ".join(tels)
        if telefono_emisor: telefono_emisor = f"TEL: {telefono_emisor}"
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
            
        builder.draw_text(iva_emisor, 162.5, y_emisor + 45, font_name="Helvetica-Bold", font_size=9, align="center")

    # COMPROBANTE (Right)
    titulo_cbte = get_titulo_comprobante(codigo, venta.tipo.detalle if venta.tipo else 'Comprobante')
    if layout_style == 'PRE': titulo_cbte = "PRESUPUESTO"
    
    builder.draw_text(titulo_cbte, 431.25, 65, font_name="Helvetica-Bold", font_size=18, align="center")
    
    builder.draw_text("Punto:", 330, 95, font_name="Helvetica-Bold", font_size=10)
    builder.draw_text(f"{venta.punto:05d}", 365, 95, font_size=10)
    
    builder.draw_text("Comp. Nro:", 410, 95, font_name="Helvetica-Bold", font_size=10)
    builder.draw_text(f"{venta.numero:08d}", 475, 95, font_size=10)
    
    builder.draw_text("Fecha de Emision:", 330, 115, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text(venta.fecha.strftime('%d/%m/%Y'), 420, 115, font_size=9)
    
    if layout_style != 'PRE':
        builder.draw_text("CUIT:", 330, 130, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(empresa.cuit, 360, 130, font_size=9)
        
        builder.draw_text("Ingresos Brutos:", 330, 145, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(empresa.cuit, 410, 145, font_size=9)
        
        builder.draw_text("Fecha de Inicio de Actividades:", 330, 160, font_name="Helvetica-Bold", font_size=9)
        inicio_emisor = empresa.fecha_inicio_actividades.strftime('%d/%m/%Y') if empresa.fecha_inicio_actividades else "01/01/2000"
        builder.draw_text(inicio_emisor, 470, 160, font_size=9)
    else:
        builder.draw_text("DOCUMENTO NO VALIDO COMO FACTURA", 162.5, 100, font_name="Helvetica-Bold", font_size=10, align="center")

    # === CLIENT DATA ===
    dom_cliente = get_domicilio_completo_cliente(venta, cliente)
    
    if layout_style != 'PRE':
        builder.draw_text("CUIT:", 25, 190, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.cliente_cuit or cliente.cuit or '', 55, 190, font_size=9)
        
        builder.draw_text("Apellido y Nombres / Razon Social:", 160, 190, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.cliente_razon_social or cliente.razon_social, 325, 190, font_size=9)
        
        builder.draw_text("Domicilio:", 25, 210, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(dom_cliente, 75, 210, font_size=9)
        
        builder.draw_text("Condicion frente al IVA:", 25, 230, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(cliente.condicion_iva, 135, 230, font_size=9)
        
        cond_venta = "Contado" if (venta.efectivo > 0 or venta.transferencia > 0 or venta.tarjeta > 0) else "Cuenta Corriente"
        builder.draw_text("Condicion de venta:", 340, 230, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(cond_venta, 435, 230, font_size=9)
        
        # Periodos
        builder.draw_text("Periodo Facturado Desde:", 25, 250, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.fecha.strftime('%d/%m/%Y'), 145, 250, font_size=9)
        
        builder.draw_text("Hasta:", 230, 250, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.fecha.strftime('%d/%m/%Y'), 265, 250, font_size=9)
        
        builder.draw_text("Fecha de Vto. para el Pago:", 350, 250, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.fecha.strftime('%d/%m/%Y'), 485, 250, font_size=9)
    else:
        builder.draw_text("Apellido y Nombres / Razon Social:", 25, 195, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(venta.cliente_razon_social or cliente.razon_social, 195, 195, font_size=9)
        
        builder.draw_text("Domicilio:", 25, 215, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text(dom_cliente, 75, 215, font_size=9)
        
        builder.draw_text("Condicion de venta:", 25, 250, font_name="Helvetica-Bold", font_size=9)
        builder.draw_text("Cuenta Corriente", 125, 250, font_size=9)

    # === ITEMS HEADER ===
    builder.draw_text("Codigo", 25, 270, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text("Detalle", 85, 270, font_name="Helvetica-Bold", font_size=9)
    builder.draw_text("Cantidad", 385, 270, font_name="Helvetica-Bold", font_size=9, align="right")
    builder.draw_text("Precio Unit.", 475, 270, font_name="Helvetica-Bold", font_size=9, align="right")
    builder.draw_text("Importe", 565, 270, font_name="Helvetica-Bold", font_size=9, align="right")
    
    from reportlab.lib.utils import simpleSplit
    # === ITEMS ROWS ===
    y_items = 290
    for item in venta.items.all():
        codigo_str = str(item.producto_id) if item.producto_id else ""
        concepto_str = item.concepto or (item.producto.detalle if hasattr(item, 'producto') and item.producto else "")
        
        if hasattr(item, 'producto') and item.producto:
            item_subproductos = [sp for sp in venta.subproductos.all() if sp.producto_id == item.producto_id]
            
            # Fallback para comprobantes sin trazabilidad directa (ej. Remitos) pero facturados el mismo día al mismo cliente
            if not item_subproductos:
                from productos.models import Subproducto
                item_subproductos = Subproducto.objects.filter(
                    producto_id=item.producto_id,
                    venta__cliente_id=venta.cliente_id,
                    venta__fecha=venta.fecha
                )
                
            for sp in item_subproductos:
                extras = []
                if sp.serie: extras.append(f"Serie: {sp.serie.strip()}")
                if sp.cuim: extras.append(f"Cuim: {sp.cuim.strip()}")
                if extras:
                    concepto_str += f"\n{' - '.join(extras)}"
                    
        cant_str = format_arg(item.cantidad)
        precio_str = format_arg(item.precio_unitario)
        total_str = format_arg(item.total)
        
        # Envolvemos el concepto_str en varias líneas para que no pise columnas.
        # Ancho disponible: aprox 280 puntos (desde 85 hasta 365)
        lines = simpleSplit(concepto_str, "Helvetica", 9, 270)
        
        # Dibujamos las columnas de valor una sola vez en la primera línea
        builder.draw_text(codigo_str, 25, y_items, font_size=9)
        builder.draw_text(cant_str, 385, y_items, font_size=9, align="right")
        builder.draw_text(precio_str, 475, y_items, font_size=9, align="right")
        builder.draw_text(total_str, 565, y_items, font_size=9, align="right")
        
        if not lines:
            y_items += 15
        else:
            for line in lines:
                builder.draw_text(line, 85, y_items, font_size=9)
                y_items += 12
            y_items += 3  # Espaciado extra al final del ítem

    # === FOOTER (TOTALES) ===
    if layout_style == 'A':
        builder.draw_text("NETO GRAVADO:", 470, 715, font_name="Helvetica-Bold", font_size=9, align="right")
        builder.draw_text(format_arg(venta.neto), 565, 715, font_size=9, align="right")
        
        active_alics = [a for a in venta.alicuotas_iva.all() if a.base_imponible > 0 or a.importe_iva > 0]
        if not active_alics and venta.iva > 0:
            class FakeAlic:
                def __init__(self, alic, iva_val):
                    self.alicuota = alic
                    self.importe_iva = iva_val

            alicuotas_dict = {}
            for item in venta.items.all():
                alic = item.iva_alicuota or Decimal('0.00')
                if alic > 0:
                    alicuotas_dict[alic] = alicuotas_dict.get(alic, Decimal('0.00')) + item.total

            active_alics = []
            if alicuotas_dict:
                for alic, gross_total in sorted(alicuotas_dict.items(), reverse=True):
                    base = gross_total / (Decimal('1') + alic / Decimal('100'))
                    active_alics.append(FakeAlic(alic, gross_total - base))
                
                # Ajuste de redondeo contra el total de IVA real de la factura
                sum_iva = sum(a.importe_iva for a in active_alics)
                diff = venta.iva - sum_iva
                if abs(diff) > Decimal('0.00') and abs(diff) < Decimal('2.00'):
                    active_alics[0].importe_iva += diff
            else:
                active_alics = [FakeAlic(Decimal('21.00'), venta.iva)]
            
        y_iva = 730
        if active_alics:
            for alic in active_alics:
                builder.draw_text("IVA:", 430, y_iva, font_name="Helvetica-Bold", font_size=9, align="right")
                builder.draw_text(f"{format_arg(alic.alicuota)} %", 480, y_iva, font_size=9, align="right")
                builder.draw_text(format_arg(alic.importe_iva), 565, y_iva, font_size=9, align="right")
                y_iva += 15
        else:
            builder.draw_text("IVA:", 430, y_iva, font_name="Helvetica-Bold", font_size=9, align="right")
            builder.draw_text("0.00 %", 480, y_iva, font_size=9, align="right")
            builder.draw_text("0.00", 565, y_iva, font_size=9, align="right")
            
        builder.draw_text("TOTAL FACTURADO:", 470, 785, font_name="Helvetica-Bold", font_size=10, align="right")
        builder.draw_text(format_arg(venta.total), 565, 785, font_name="Helvetica-Bold", font_size=10, align="right")
        
        if venta.cae:
            builder.draw_text("CAE:", 160, 765, font_name="Helvetica-Bold", font_size=9, align="right")
            builder.draw_text(venta.cae, 170, 765, font_size=9)
        if venta.vto_cae:
            builder.draw_text("Vto.CAE:", 160, 780, font_name="Helvetica-Bold", font_size=9, align="right")
            builder.draw_text(venta.vto_cae.strftime('%d/%m/%Y'), 170, 780, font_size=9)
            
    elif layout_style == 'B':
        # Régimen de Transparencia Fiscal
        builder.draw_text("Régimen de Transparencia Fiscal al Consumidor (Ley 27.743)", 90, 715, font_name="Helvetica", font_size=9)
        builder.draw_line(90, 717, 345, 717)
        
        builder.draw_text("IVA Contenido:", 265, 730, font_name="Helvetica", font_size=9, align="right")
        builder.draw_text(format_arg(venta.iva), 315, 730, font_size=9, align="right")
        
        builder.draw_text("Otros Impuestos Nacionales Indirectos:", 265, 745, font_name="Helvetica", font_size=9, align="right")
        builder.draw_text("0.00", 315, 745, font_size=9, align="right")
        
        builder.draw_text("SUBTOTAL:", 470, 745, font_name="Helvetica-Bold", font_size=9, align="right")
        builder.draw_text(format_arg(venta.neto + venta.iva), 565, 745, font_size=9, align="right")
        
        builder.draw_text("TOTAL FACTURADO:", 470, 785, font_name="Helvetica-Bold", font_size=10, align="right")
        builder.draw_text(format_arg(venta.total), 565, 785, font_name="Helvetica-Bold", font_size=10, align="right")
        
        if venta.cae:
            builder.draw_text("CAE:", 160, 765, font_name="Helvetica-Bold", font_size=9, align="right")
            builder.draw_text(venta.cae, 170, 765, font_size=9)
        if venta.vto_cae:
            builder.draw_text("Vto.CAE:", 160, 780, font_name="Helvetica-Bold", font_size=9, align="right")
            builder.draw_text(venta.vto_cae.strftime('%d/%m/%Y'), 170, 780, font_size=9)
            
    else:
        builder.draw_text("TOTAL PRESUPUESTADO:", 470, 785, font_name="Helvetica-Bold", font_size=10, align="right")
        builder.draw_text(format_arg(venta.total), 565, 785, font_name="Helvetica-Bold", font_size=10, align="right")

    # === CÓDIGO QR ===
    if layout_style in ['A', 'B'] and (venta.cod_qr or venta.cae):
        qr_data = venta.cod_qr or f"https://www.afip.gob.ar/fe/qr/?p={venta.cae}"
        if qr_data:
            try:
                import qrcode
                from reportlab.lib.utils import ImageReader
                qr = qrcode.QRCode(version=1, box_size=10, border=0)
                qr.add_data(qr_data)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_io = io.BytesIO()
                qr_img.save(qr_io, format='PNG')
                qr_io.seek(0)
                
                qr_y = 715 if layout_style == 'A' else 735 # Desplazamos QR en la B para la Ley de Transparencia
                builder.draw_image(qr_io, 25, qr_y, 60, 60)
            except Exception as e:
                logger.warning(f"Error al generar el código QR: {e}")

    builder.save()
    packet.seek(0)
    return packet.read()
