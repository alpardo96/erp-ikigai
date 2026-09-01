from django.db import transaction
from django.db.models import Sum
from datetime import date
from decimal import Decimal

from contable.models import Asiento, AsientoLinea, Cuenta, ParametrosContables
from empresas.models import Ejercicio

@transaction.atomic
def procesar_cierre_ejercicio(ejercicio_id, empresa_id, usuario):
    """
    Realiza el cierre contable del ejercicio:
    1. Obtiene todas las cuentas de Resultado (R) con saldo.
    2. Genera un asiento compensador para dejarlas en cero.
    3. La diferencia se imputa a la cuenta 'Resultado del Ejercicio'.
    """
    ejercicio = Ejercicio.objects.get(pk=ejercicio_id, empresa_id=empresa_id)
    
    # Validar si ya existe una refundición para este ejercicio.
    # Se identifica por condic=6, no por el texto del concepto: el concepto es editable y un
    # `icontains` deja pasar duplicados ante el mínimo cambio de redacción.
    if Asiento.objects.filter(ejercicio=ejercicio, condic=6, anulado=False).exists():
        raise ValueError(f"Ya existe un asiento de refundición activo para el ejercicio {ejercicio.ejercicio}.")
    
    # Obtener la cuenta de Resultado del Ejercicio
    parametros = ParametrosContables.objects.filter(empresa_id=empresa_id).first()
    if not parametros or not parametros.cta_resultado_ejercicio:
        raise ValueError("No se ha configurado la cuenta 'Resultado del Ejercicio' en los Parámetros Contables.")
    
    cta_resultado = parametros.cta_resultado_ejercicio
    
    # Obtener saldos de cuentas de resultado
    cuentas_resultado = Cuenta.objects.filter(empresa_id=empresa_id, tipo='R', imputable=1)
    
    lineas_asiento = []
    total_debe = Decimal('0.00')
    total_haber = Decimal('0.00')
    
    for cuenta in cuentas_resultado:
        saldos = AsientoLinea.objects.filter(
            cuenta=cuenta,
            asiento__ejercicio=ejercicio,
            asiento__anulado=False
        ).aggregate(
            t_debe=Sum('debe', default=0),
            t_haber=Sum('haber', default=0)
        )
        
        saldo_deudor = saldos['t_debe'] - saldos['t_haber']
        
        if saldo_deudor > 0:
            # La cuenta tiene saldo deudor, debemos acreditarla
            lineas_asiento.append({
                'cuenta': cuenta,
                'leyenda': f"Cierre de Ejercicio {ejercicio.ejercicio}",
                'debe': Decimal('0.00'),
                'haber': saldo_deudor
            })
            total_haber += saldo_deudor
        elif saldo_deudor < 0:
            # La cuenta tiene saldo acreedor, debemos debitarla
            saldo_acreedor = abs(saldo_deudor)
            lineas_asiento.append({
                'cuenta': cuenta,
                'leyenda': f"Cierre de Ejercicio {ejercicio.ejercicio}",
                'debe': saldo_acreedor,
                'haber': Decimal('0.00')
            })
            total_debe += saldo_acreedor
            
    if not lineas_asiento:
        raise ValueError("No hay movimientos en cuentas de resultado para este ejercicio.")
        
    # Calcular resultado del ejercicio (Ganancia o Pérdida)
    # Si debitamos más de lo que acreditamos en las cuentas de resultado (ingresos > egresos), 
    # la diferencia debe ir al HABER de la cuenta Resultado del Ejercicio.
    
    diferencia = total_debe - total_haber
    
    if diferencia > 0:
        lineas_asiento.append({
            'cuenta': cta_resultado,
            'leyenda': f"Resultado del Ejercicio {ejercicio.ejercicio} (Ganancia)",
            'debe': Decimal('0.00'),
            'haber': diferencia
        })
        total_haber += diferencia
    elif diferencia < 0:
        lineas_asiento.append({
            'cuenta': cta_resultado,
            'leyenda': f"Resultado del Ejercicio {ejercicio.ejercicio} (Pérdida)",
            'debe': abs(diferencia),
            'haber': Decimal('0.00')
        })
        total_debe += abs(diferencia)
        
    # Crear el asiento
    fecha_cierre = ejercicio.cierre
    
    asiento = Asiento.objects.create(
        empresa_id=empresa_id,
        ejercicio=ejercicio,
        fecha=fecha_cierre,
        concepto=f"CIERRE DE EJERCICIO {ejercicio.ejercicio}",
        monto=total_debe, # total_debe == total_haber
        modulo=1, # Manual/Contabilidad
        # condic=6 (Refundición): este asiento cancela las cuentas de RESULTADO contra la cuenta
        # Resultado del Ejercicio. NO es el asiento de cierre (condic=7), que además cancela las
        # patrimoniales y todavía no está implementado. Sin este condic el asiento quedaría con el
        # default 1 (Real) y contaminaría el último mes de todo reporte de evolución mensual,
        # dando vuelta las cuentas de resultado.
        condic=6
    )
    
    orden = 1
    for linea in lineas_asiento:
        AsientoLinea.objects.create(
            asiento=asiento,
            orden=orden,
            cuenta=linea['cuenta'],
            leyenda=linea['leyenda'],
            debe=linea['debe'],
            haber=linea['haber']
        )
        orden += 1
        
    return asiento
