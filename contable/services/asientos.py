from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from typing import List, Dict, Any

from empresas.models import Empresa, Ejercicio
from contable.models import (
    Asiento, AsientoLinea, Cuenta, CONDIC_ASIENTO, CONDIC_ESTRUCTURAL,
)

@transaction.atomic
def crear_asiento(
    empresa: Empresa,
    fecha,
    concepto: str,
    lineas: List[Dict[str, Any]],
    condic: int = 1,
    modulo: int = 1,
    cli_pro = None,
    fec_vto = None,
    ejercicio = None,
    usuario = None
) -> Asiento:
    """
    Crea un asiento contable de forma atÃ³mica y valida que cumpla con la partida doble
    y que use Ãºnicamente cuentas contables imputables pertenecientes a la empresa.
    
    Cada elemento en `lineas` debe ser un diccionario con la estructura:
    {
        'cuenta': Cuenta (o int cuenta_id),
        'debe': Decimal (opcional, default 0),
        'haber': Decimal (opcional, default 0),
        'leyenda': str (opcional, default ""),
        'divisa': str (opcional, default 'PES'),
        'cotizacion': Decimal (opcional, default 1.0),
        'debe_divisa': Decimal (opcional, default 0),
        'haber_divisa': Decimal (opcional, default 0),
        'fec_vto': Date (opcional, default None),
        'cli_pro': ClienteProveedor (opcional, default None)
    }
    """
    if not lineas:
        raise ValidationError("El asiento debe contener al menos una lÃ­nea de movimiento.")
        
    # 1. Resolver Ejercicio Fiscal si no se provee
    if not ejercicio:
        ejercicio = Ejercicio.objects.filter(
            empresa=empresa,
            inicio__lte=fecha,
            cierre__gte=fecha
        ).first()
        if not ejercicio:
            raise ValidationError(
                f"No se encontrÃ³ un ejercicio fiscal activo para la fecha {fecha.strftime('%d/%m/%Y')} en la empresa {empresa.nombre}."
            )
            
    # 2. Validar partida doble y acumular montos
    debe_total = Decimal("0.00")
    haber_total = Decimal("0.00")
    
    processed_lineas = []
    for idx, linea in enumerate(lineas):
        # Resolver cuenta
        cuenta_obj = linea.get('cuenta')
        if isinstance(cuenta_obj, int) or isinstance(cuenta_obj, str):
            cuenta = Cuenta.objects.filter(pk=int(cuenta_obj), empresa=empresa).first()
        elif isinstance(cuenta_obj, Cuenta):
            cuenta = cuenta_obj
        else:
            cuenta = None
            
        if not cuenta:
            raise ValidationError(f"LÃ­nea {idx + 1}: La cuenta contable especificada no existe o no pertenece a la empresa.")
            
        if cuenta.imputable != 1:
            raise ValidationError(
                f"LÃ­nea {idx + 1}: La cuenta '{cuenta.cuenta}' ({cuenta.jerarquia}) no es imputable y no puede recibir movimientos."
            )
            
        debe = Decimal(str(linea.get('debe', 0) or 0))
        haber = Decimal(str(linea.get('haber', 0) or 0))
        
        if debe < 0 or haber < 0:
            raise ValidationError(f"LÃ­nea {idx + 1}: Los montos de Debe y Haber no pueden ser negativos.")
            
        if debe > 0 and haber > 0:
            raise ValidationError(
                f"LÃ­nea {idx + 1}: Una lÃ­nea no puede tener importes en el Debe y en el Haber simultÃ¡neamente."
            )
            
        debe_total += debe
        haber_total += haber
        
        # Multimoneda
        divisa = linea.get('divisa', 'PES')
        cotizacion = Decimal(str(linea.get('cotizacion', 1.0) or 1.0))
        debe_divisa = Decimal(str(linea.get('debe_divisa', 0) or 0))
        haber_divisa = Decimal(str(linea.get('haber_divisa', 0) or 0))
        
        processed_lineas.append({
            'orden': idx + 1,
            'cuenta': cuenta,
            'leyenda': linea.get('leyenda', '') or '',
            'debe': debe,
            'haber': haber,
            'divisa': divisa,
            'cotizacion': cotizacion,
            'debe_divisa': debe_divisa,
            'haber_divisa': haber_divisa,
            'fec_vto': linea.get('fec_vto'),
            'cli_pro': linea.get('cli_pro')
        })
        
    # Validar balance
    if debe_total != haber_total:
        raise ValidationError(
            f"El asiento estÃ¡ desbalanceado. Suma Debe: {debe_total} - Suma Haber: {haber_total}."
        )
        
    # 3. Crear Cabecera del Asiento
    asiento = Asiento.objects.create(
        empresa=empresa,
        ejercicio=ejercicio,
        fecha=fecha,
        concepto=concepto,
        condic=condic,
        monto=debe_total,
        modulo=modulo,
        cli_pro=cli_pro,
        fec_vto=fec_vto,
        creado_por=usuario,
        modificado_por=usuario
    )
    
    # 4. Crear LÃ­neas en Lote
    lineas_db = [
        AsientoLinea(
            asiento=asiento,
            orden=l['orden'],
            cuenta=l['cuenta'],
            leyenda=l['leyenda'],
            debe=l['debe'],
            haber=l['haber'],
            divisa=l['divisa'],
            cotizacion=l['cotizacion'],
            debe_divisa=l['debe_divisa'],
            haber_divisa=l['haber_divisa'],
            fec_vto=l['fec_vto'],
            cli_pro=l['cli_pro']
        )
        for l in processed_lineas
    ]
    
    AsientoLinea.objects.bulk_create(lineas_db)
    
    return asiento

@transaction.atomic
def editar_asiento(
    asiento: Asiento,
    fecha,
    concepto: str,
    lineas: List[Dict[str, Any]],
    usuario=None
) -> Asiento:
    if not lineas:
        raise ValidationError("El asiento debe contener al menos una línea de movimiento.")

    # Los asientos estructurales (5=Apertura, 6=Refundición, 7=Cierre) los genera un proceso del
    # sistema y no se retocan a mano: se anulan y se vuelve a correr el proceso. Además el form
    # de edición sólo ofrece condic 1 y 2, así que guardar uno de éstos lo degradaría a Real.
    if asiento.condic in CONDIC_ESTRUCTURAL:
        nombre = dict(CONDIC_ASIENTO).get(asiento.condic, asiento.condic)
        raise ValidationError(
            f"El asiento {asiento.asiento_id} es de tipo '{nombre}' y lo genera el sistema: "
            f"no se edita. Anulelo y vuelva a ejecutar el proceso que lo creó."
        )

    # La fecha no puede sacar al asiento de su ejercicio. `crear_asiento` deriva el ejercicio
    # DESDE la fecha, así que al nacer el invariante se cumple; sin esta validación la edición
    # lo rompía y dejaba el asiento contado dentro del ejercicio por su FK pero fuera de su
    # rango de fechas.
    ejercicio = asiento.ejercicio
    if ejercicio and not (ejercicio.inicio <= fecha <= ejercicio.cierre):
        raise ValidationError(
            f"La fecha {fecha.strftime('%d/%m/%Y')} está fuera del ejercicio "
            f"'{ejercicio.ejercicio}' ({ejercicio.inicio.strftime('%d/%m/%Y')} - "
            f"{ejercicio.cierre.strftime('%d/%m/%Y')}), al que pertenece este asiento."
        )

    debe_total = Decimal("0.00")
    haber_total = Decimal("0.00")

    processed_lineas = []
    for idx, linea in enumerate(lineas):
        cuenta_obj = linea.get('cuenta')
        if isinstance(cuenta_obj, int) or isinstance(cuenta_obj, str):
            cuenta = Cuenta.objects.filter(pk=int(cuenta_obj), empresa=asiento.empresa).first()
        elif isinstance(cuenta_obj, Cuenta):
            cuenta = cuenta_obj
        else:
            cuenta = None
            
        if not cuenta:
            raise ValidationError(f"Línea {idx + 1}: La cuenta contable especificada no existe o no pertenece a la empresa.")
            
        if cuenta.imputable != 1:
            raise ValidationError(f"Línea {idx + 1}: La cuenta '{cuenta.cuenta}' ({cuenta.jerarquia}) no es imputable y no puede recibir movimientos.")
            
        debe = Decimal(str(linea.get('debe', 0) or 0))
        haber = Decimal(str(linea.get('haber', 0) or 0))
        
        if debe < 0 or haber < 0:
            raise ValidationError(f"Línea {idx + 1}: Los montos de Debe y Haber no pueden ser negativos.")
            
        if debe > 0 and haber > 0:
            raise ValidationError(f"Línea {idx + 1}: Una línea no puede tener importes en el Debe y en el Haber simultáneamente.")
            
        debe_total += debe
        haber_total += haber
        
        divisa = linea.get('divisa', 'PES')
        cotizacion = Decimal(str(linea.get('cotizacion', 1.0) or 1.0))
        debe_divisa = Decimal(str(linea.get('debe_divisa', 0) or 0))
        haber_divisa = Decimal(str(linea.get('haber_divisa', 0) or 0))
        
        processed_lineas.append({
            'orden': idx + 1,
            'cuenta': cuenta,
            'leyenda': linea.get('leyenda', '')[:255] or '',
            'debe': debe,
            'haber': haber,
            'divisa': divisa,
            'cotizacion': cotizacion,
            'debe_divisa': debe_divisa,
            'haber_divisa': haber_divisa,
            'fec_vto': linea.get('fec_vto'),
            'cli_pro': linea.get('cli_pro')
        })
        
    debe_total = debe_total.quantize(Decimal("0.01"))
    haber_total = haber_total.quantize(Decimal("0.01"))
    if abs(debe_total - haber_total) > Decimal("0.01"):
        raise ValidationError(f"El asiento no balancea. Debe: $ {debe_total} | Haber: $ {haber_total} | Diferencia: $ {abs(debe_total - haber_total)}")
        
    asiento.fecha = fecha
    asiento.concepto = concepto
    asiento.save(update_fields=['fecha', 'concepto'])
    
    asiento.lineas.all().delete()
    
    lineas_a_crear = [
        AsientoLinea(
            asiento=asiento,
            **pl
        ) for pl in processed_lineas
    ]
    AsientoLinea.objects.bulk_create(lineas_a_crear)
    
    # Sincronizar cta_imputacion de Compra si es un Asiento de Compras
    if asiento.modulo == 5:
        from facturacion.models import Compra
        from contable.models import ParametrosContables
        
        compra = Compra.objects.filter(asiento_id=asiento.asiento_id).first()
        if compra:
            parametros = ParametrosContables.objects.filter(empresa=asiento.empresa).first()
            cta_iva_compras_id = parametros.cta_iva_compras_id if parametros else None
            
            # Buscar la cuenta principal de gasto (Debe > 0, excluyendo IVA)
            main_expense_line = asiento.lineas.filter(debe__gt=0).exclude(cuenta_id=cta_iva_compras_id).order_by('-debe').first()
            if main_expense_line:
                compra.cta_imputacion = main_expense_line.cuenta_id
                compra.save(update_fields=['cta_imputacion'])
    
    return asiento

