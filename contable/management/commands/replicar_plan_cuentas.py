"""
Comando de gestión de Django para replicar el Plan de Cuentas (Cuenta) y los
Parámetros Contables (ParametrosContables) de una empresa a otra.
"""
import os
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from contable.models import Cuenta, ParametrosContables
from tesoreria.models import MedioPago, CuentaBancaria
from empresas.models import Empresa


class Command(BaseCommand):
    help = 'Replica el plan de cuentas, parámetros contables, medios de pago y cuentas bancarias de una empresa a otra'

    def add_arguments(self, parser):
        parser.add_argument(
            '--origen',
            type=int,
            default=1,
            help='ID de la Empresa origen (default: 1)'
        )
        parser.add_argument(
            '--destino',
            type=int,
            default=3,
            help='ID de la Empresa destino (default: 3)'
        )

    def handle(self, *args, **options):
        origen_id = options['origen']
        destino_id = options['destino']

        if origen_id == destino_id:
            raise CommandError("La empresa origen y la empresa destino no pueden ser la misma.")

        self.stdout.write(f"[{datetime.now()}] Iniciando replicación de Plan de Cuentas: Empresa {origen_id} -> Empresa {destino_id}")

        try:
            empresa_origen = Empresa.objects.get(id=origen_id)
        except Empresa.DoesNotExist:
            raise CommandError(f"ERROR: La Empresa origen con ID={origen_id} no existe en la base de datos.")

        try:
            empresa_destino = Empresa.objects.get(id=destino_id)
        except Empresa.DoesNotExist:
            raise CommandError(f"ERROR: La Empresa destino con ID={destino_id} no existe en la base de datos.")

        with transaction.atomic():
            # Pasada 1: Cargar todas las cuentas origen ordenadas jerárquicamente
            cuentas_origen = list(Cuenta.objects.filter(empresa=empresa_origen).order_by('jerarquia', 'id'))
            if not cuentas_origen:
                raise CommandError(f"La Empresa origen '{empresa_origen.nombre}' (ID={origen_id}) no posee cuentas contables.")

            self.stdout.write(f"Empresa Origen '{empresa_origen.nombre}': {len(cuentas_origen)} cuentas contables encontradas.")

            # Cargar cuentas existentes en la empresa destino para evitar consultas N+1
            cuentas_destino_map = {c.jerarquia: c for c in Cuenta.objects.filter(empresa=empresa_destino)}
            mapa_cuentas = {}  # Mapeo: {cuenta_origen_id: nueva_cuenta_destino}
            cuentas_creadas = 0
            cuentas_actualizadas = 0

            # Crear o sincronizar cuentas clonadas para la empresa destino
            for cta in cuentas_origen:
                if cta.jerarquia in cuentas_destino_map:
                    cuenta_clon = cuentas_destino_map[cta.jerarquia]
                    cuenta_clon.codigo = cta.codigo
                    cuenta_clon.cuenta = cta.cuenta
                    cuenta_clon.imputable = cta.imputable
                    cuenta_clon.tipo = cta.tipo
                    cuenta_clon.rg_830 = cta.rg_830
                    cuenta_clon.id_pre = cta.id_pre
                    cuenta_clon.id_bce = cta.id_bce
                    cuenta_clon.id_ec = cta.id_ec
                    cuenta_clon.id_fc = cta.id_fc
                    cuenta_clon.tipo_disponibilidad = cta.tipo_disponibilidad
                    cuenta_clon.save()
                    cuentas_actualizadas += 1
                else:
                    cuenta_clon = Cuenta.objects.create(
                        empresa=empresa_destino,
                        jerarquia=cta.jerarquia,
                        codigo=cta.codigo,
                        cuenta=cta.cuenta,
                        imputable=cta.imputable,
                        tipo=cta.tipo,
                        rg_830=cta.rg_830,
                        id_pre=cta.id_pre,
                        id_bce=cta.id_bce,
                        id_ec=cta.id_ec,
                        id_fc=cta.id_fc,
                        tipo_disponibilidad=cta.tipo_disponibilidad,
                    )
                    cuentas_creadas += 1

                # Mapeamos la equivalencia de ID origen -> objeto destino
                mapa_cuentas[cta.id] = cuenta_clon

            self.stdout.write(self.style.SUCCESS(f"Fase 1 completada: {cuentas_creadas} creadas, {cuentas_actualizadas} actualizadas en '{empresa_destino.nombre}'."))

            # Pasada 2: Asignar relaciones jerárquicas (sumariza)
            relaciones_actualizadas = 0
            for cta in cuentas_origen:
                if cta.sumariza_id and cta.sumariza_id in mapa_cuentas:
                    cuenta_clon = mapa_cuentas[cta.id]
                    padre_clon = mapa_cuentas[cta.sumariza_id]
                    if cuenta_clon.sumariza_id != padre_clon.id:
                        cuenta_clon.sumariza = padre_clon
                        cuenta_clon.save(update_fields=['sumariza'])
                        relaciones_actualizadas += 1

            self.stdout.write(self.style.SUCCESS(f"Fase 2 completada: {relaciones_actualizadas} relaciones jerárquicas ('sumariza') vinculadas."))

            # Pasada 3: Replicar Parámetros Contables
            param_origen = ParametrosContables.objects.filter(empresa=empresa_origen).first()
            param_destino = None
            if param_origen:
                param_destino, created_p = ParametrosContables.objects.get_or_create(empresa=empresa_destino)

                # Nombres de todas las claves foráneas en ParametrosContables que referencian a Cuenta
                cuenta_fk_fields = [
                    'cta_iva_credito', 'cta_iva_debito',
                    'cta_ret_iva', 'cta_ret_ganancias', 'cta_ret_iibb', 'cta_ret_suss', 'cta_ret_mun',
                    'cta_ret_practicada_ganancias', 'cta_ret_practicada_iva', 'cta_ret_practicada_iibb', 'cta_ret_practicada_suss',
                    'cta_caja', 'cta_dolar', 'cta_caja_mostrador', 'cta_caja_mostrador_dolares',
                    'cta_caja_central', 'cta_caja_central_dolares', 'cta_transferencias_sucursal',
                    'cta_valores_cartera', 'cta_tarjetas_a_cobrar', 'cta_diferencia_caja',
                    'cta_ventas', 'cta_compras', 'cta_clientes_default', 'cta_proveedores_default',
                    'cta_impuestos_internos', 'cta_itc', 'cta_bonificaciones', 'cta_descuentos_obtenidos',
                    'cta_resultado_ejercicio'
                ]

                fk_mapeadas = 0
                for field_name in cuenta_fk_fields:
                    cta_orig = getattr(param_origen, field_name)
                    if cta_orig and cta_orig.id in mapa_cuentas:
                        setattr(param_destino, field_name, mapa_cuentas[cta_orig.id])
                        fk_mapeadas += 1
                    else:
                        setattr(param_destino, field_name, None)

                param_destino.metodo_contabilizacion_ventas = param_origen.metodo_contabilizacion_ventas
                param_destino.save()

                accion_p = "creados" if created_p else "actualizados"
                self.stdout.write(self.style.SUCCESS(f"Fase 3 completada: Parámetros Contables {accion_p} con {fk_mapeadas} cuentas mapeadas."))

            # Pasada 4: Replicación de Medios de Pago desde la Empresa Origen (o CSV como fallback)
            medios_pago_origen = MedioPago.objects.filter(empresa=empresa_origen)
            if medios_pago_origen.exists():
                self.stdout.write(f"Fase 4: Replicando Medios de Pago desde Empresa '{empresa_origen.nombre}'...")
                medios_procesados = 0
                for mp in medios_pago_origen:
                    cta_clon = mapa_cuentas.get(mp.cuenta_contable_id) if mp.cuenta_contable_id else None
                    mp_obj, created_mp = MedioPago.objects.get_or_create(
                        empresa=empresa_destino,
                        codigo=mp.codigo,
                        defaults={
                            'nombre': mp.nombre,
                            'categoria': mp.categoria,
                            'cuenta_contable': cta_clon,
                            'activo': mp.activo
                        }
                    )
                    if not created_mp:
                        mp_obj.nombre = mp.nombre
                        mp_obj.categoria = mp.categoria
                        mp_obj.cuenta_contable = cta_clon
                        mp_obj.activo = mp.activo
                        mp_obj.save()
                    medios_procesados += 1
                self.stdout.write(self.style.SUCCESS(f"Fase 4 completada: {medios_procesados} Medios de Pago replicados en '{empresa_destino.nombre}'."))
            else:
                csv_medios = r'd:\borrador\medios_pagos.csv'
                if os.path.exists(csv_medios) and param_destino:
                    self.stdout.write(f"Fase 4: Procesando Medios de Pago desde '{csv_medios}'...")
                    with open(csv_medios, 'r', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        medios_procesados = 0
                        for row in reader:
                            codigo = row['codigo'].strip()
                            nombre = row['nombre'].strip()
                            categoria = row['categoria'].strip()

                            # Determinación certera de cuenta contable según la categoría y código
                            cta_vinculada = None
                            if categoria == 'EFE':
                                cta_vinculada = param_destino.cta_caja_mostrador or param_destino.cta_caja
                            elif categoria == 'CHQ':
                                cta_vinculada = param_destino.cta_valores_cartera
                            elif categoria == 'TRA':
                                cta_vinculada = Cuenta.objects.filter(empresa=empresa_destino, cuenta__icontains='BANCO PATAGONIA').first() or param_destino.cta_caja_central
                            elif categoria == 'RET':
                                if 'GAN' in codigo:
                                    cta_vinculada = param_destino.cta_ret_ganancias
                                elif 'IIBB' in codigo:
                                    cta_vinculada = param_destino.cta_ret_iibb
                                elif 'IVA' in codigo:
                                    cta_vinculada = param_destino.cta_ret_iva

                            mp_obj, created_mp = MedioPago.objects.get_or_create(
                                empresa=empresa_destino,
                                codigo=codigo,
                                defaults={
                                    'nombre': nombre,
                                    'categoria': categoria,
                                    'cuenta_contable': cta_vinculada,
                                    'activo': True
                                }
                            )
                            if not created_mp:
                                mp_obj.nombre = nombre
                                mp_obj.categoria = categoria
                                mp_obj.cuenta_contable = cta_vinculada
                                mp_obj.activo = True
                                mp_obj.save()
                            medios_procesados += 1

                    self.stdout.write(self.style.SUCCESS(f"Fase 4 completada: {medios_procesados} Medios de Pago procesados desde CSV en '{empresa_destino.nombre}'."))

            # Pasada 5: Replicar Cuentas Bancarias (CuentaBancaria)
            cuentas_bancarias_origen = CuentaBancaria.objects.filter(empresa=empresa_origen)
            if cuentas_bancarias_origen.exists():
                cb_creadas = 0
                for cb in cuentas_bancarias_origen:
                    cta_clon = mapa_cuentas.get(cb.cuenta_contable_id) if cb.cuenta_contable_id else None
                    cta_chq_clon = mapa_cuentas.get(cb.cuenta_contable_cheques_id) if cb.cuenta_contable_cheques_id else None

                    cb_dest, created_cb = CuentaBancaria.objects.get_or_create(
                        empresa=empresa_destino,
                        banco=cb.banco,
                        cta_numero=cb.cta_numero,
                        defaults={
                            'moneda': cb.moneda,
                            'cbu': cb.cbu,
                            'cuenta_contable': cta_clon,
                            'cuenta_contable_cheques': cta_chq_clon,
                            'banco_id': cb.banco_id,
                        }
                    )
                    if not created_cb:
                        cb_dest.moneda = cb.moneda
                        cb_dest.cbu = cb.cbu
                        cb_dest.cuenta_contable = cta_clon
                        cb_dest.cuenta_contable_cheques = cta_chq_clon
                        cb_dest.banco_id = cb.banco_id
                        cb_dest.save()
                    cb_creadas += 1
                self.stdout.write(self.style.SUCCESS(f"Fase 5 completada: {cb_creadas} Cuentas Bancarias procesadas en '{empresa_destino.nombre}'."))

        self.stdout.write(self.style.SUCCESS(f"[{datetime.now()}] Replicación finalizada con éxito."))
