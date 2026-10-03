import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from tesoreria.models import ValorTerceros, Recibo, OrdenPago

print("Actualizando Recibos (valores_terceros -> recibo)...")
actualizados_recibo = 0
for v in ValorTerceros.objects.filter(asiento_recepcion_id__isnull=False, recibo__isnull=True):
    r = Recibo.objects.filter(asiento_id=v.asiento_recepcion_id).first()
    if r:
        v.recibo_id = r.id
        v.save(update_fields=['recibo_id'])
        actualizados_recibo += 1

print(f"Recibos enlazados: {actualizados_recibo}")

print("Actualizando Ordenes de Pago (valores_terceros -> orden_pago)...")
actualizados_op = 0
for v in ValorTerceros.objects.filter(asiento_entrega_id__isnull=False, orden_pago__isnull=True):
    op = OrdenPago.objects.filter(asiento_id=v.asiento_entrega_id).first()
    if op:
        v.orden_pago_id = op.id
        v.save(update_fields=['orden_pago_id'])
        actualizados_op += 1

print(f"Ordenes de Pago enlazadas: {actualizados_op}")
