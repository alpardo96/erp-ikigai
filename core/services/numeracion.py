"""
Servicio de numeración correlativa de documentos prenumerados por el sistema.

Uso:
    from core.services.numeracion import siguiente_numero
    from core.models import ContadorDocumento

    numero = siguiente_numero(empresa, punto, ContadorDocumento.ORDEN_COMPRA)

El número se asigna al CONFIRMAR el documento (no en borrador) para no dejar huecos.
La operación bloquea la fila del contador con select_for_update() dentro de una
transacción atómica, garantizando series correlativas sin huecos ni duplicados incluso
bajo concurrencia. Debe invocarse dentro de la misma transacción en la que se persiste
el documento.
"""
from django.db import transaction

from core.models import ContadorDocumento


@transaction.atomic
def siguiente_numero(empresa, punto, tipo_documento):
    """
    Devuelve el próximo número correlativo para (empresa, punto, tipo_documento),
    incrementando el contador de forma atómica y segura ante concurrencia.

    :param empresa: instancia de empresas.Empresa (o su id).
    :param punto: entero, punto de emisión (normalmente Sucursal.punto).
    :param tipo_documento: uno de ContadorDocumento.TIPOS_DOCUMENTO.
    :return: int con el número asignado (>= 1).
    """
    empresa_id = getattr(empresa, 'pk', empresa)

    contador, _ = ContadorDocumento.objects.select_for_update().get_or_create(
        empresa_id=empresa_id,
        punto=punto,
        tipo_documento=tipo_documento,
        defaults={'ultimo_numero': 0},
    )
    contador.ultimo_numero += 1
    contador.save(update_fields=['ultimo_numero'])
    return contador.ultimo_numero


class _VentasDeTipo:
    """Envoltorio que expone `.objects` filtrado por código de comprobante.

    `auditar_correlativos` recorre `fuentes` esperando un modelo con `.objects`. PRE y
    NCI son el MISMO modelo (`Venta`) y se distinguen por el tipo, así que en lugar de
    duplicar el bucle se le pasa esto, que se comporta igual.
    """

    def __init__(self, modelo, codigo):
        self._modelo = modelo
        self._codigo = codigo

    @property
    def objects(self):
        return self._modelo.objects.filter(tipo__codigo=self._codigo)


def auditar_correlativos(empresa_id=None):
    """Verifica la integridad de las series correlativas de los documentos prenumerados
    por el sistema (OC, Informe de Recepción, Remito Interno), agrupadas por
    (empresa, punto, tipo_documento). Detecta faltantes (huecos), duplicados y desfasajes
    contra el contador. Los documentos ANULADOS conservan su número (no generan hueco).

    Devuelve una lista de dicts:
      {empresa_id, tipo, tipo_label, punto, minimo, maximo, cantidad, faltantes,
       duplicados, contador, ok}
    """
    from facturacion.models import OrdenCompra, Recepcion, RemitoInterno
    from verticalidades.distribucion.models import (ExtensionPedidoDistribucion,
                                     RecepcionDevolucion, Reparto)

    fuentes = [
        (ContadorDocumento.ORDEN_COMPRA, 'Orden de Compra', OrdenCompra, 'empresa_id'),
        (ContadorDocumento.INFORME_RECEPCION, 'Informe de Recepción', Recepcion, 'empresa_id'),
        (ContadorDocumento.REMITO_INTERNO, 'Remito Interno', RemitoInterno, 'empresa_id'),
        # Distribución (Plan 074 §4.2): el pedido es un documento emitido y su serie se
        # audita como cualquier otra. La empresa se alcanza por la preventa.
        (ContadorDocumento.PEDIDO, 'Pedido de Cliente', ExtensionPedidoDistribucion,
         'preventa__empresa_id'),
        # Los otros dos documentos que emite el módulo. El control de integridad SÓLO es
        # posible sobre lo que uno emite con numeración propia, así que dejarlos fuera de
        # esta auditoría los volvería tan inauditables como el número de un tercero.
        (ContadorDocumento.REPARTO, 'Reparto / Hoja de Ruta', Reparto, 'empresa_id'),
        (ContadorDocumento.RECEPCION_DEVOLUCION, 'Recepción de Devoluciones',
         RecepcionDevolucion, 'empresa_id'),
    ]

    # Series NO FISCALES de venta (Plan 075): se auditan filtrando `Venta` por el código
    # del tipo de comprobante. Se agregan aparte porque comparten modelo y se distinguen
    # por un filtro, no por la clase.
    from facturacion.models import Venta
    for tipo_doc, label, codigo in (
            (ContadorDocumento.VENTA_PRE, 'Presupuesto / PRE', 'PRE'),
            (ContadorDocumento.VENTA_NCI, 'Nota de Crédito Interna', 'NCI')):
        fuentes.append((tipo_doc, label, _VentasDeTipo(Venta, codigo), 'empresa_id'))

    contadores = {
        (c.empresa_id, c.punto, c.tipo_documento): c.ultimo_numero
        for c in ContadorDocumento.objects.all()
    }

    filas = []
    for tipo, label, modelo, emp_field in fuentes:
        qs = modelo.objects.exclude(numero__isnull=True)
        if empresa_id:
            qs = qs.filter(**{emp_field: empresa_id})
        # Agrupar por (empresa, punto)
        grupos = {}
        for emp_id, punto, numero in qs.values_list(emp_field, 'punto', 'numero'):
            grupos.setdefault((emp_id, punto), []).append(numero)

        for (emp_id, punto), numeros in grupos.items():
            numeros_ordenados = sorted(numeros)
            conjunto = set(numeros)
            maximo = max(numeros)
            minimo = min(numeros)
            esperados = set(range(1, maximo + 1))
            faltantes = sorted(esperados - conjunto)
            # Duplicados (no deberían existir por el unique constraint, pero se verifica)
            vistos, duplicados = set(), set()
            for n in numeros:
                if n in vistos:
                    duplicados.add(n)
                vistos.add(n)
            contador = contadores.get((emp_id, punto, tipo))
            ok = (not faltantes and not duplicados
                  and minimo == 1
                  and (contador is None or contador == maximo))
            filas.append({
                'empresa_id': emp_id, 'tipo': tipo, 'tipo_label': label, 'punto': punto,
                'minimo': minimo, 'maximo': maximo, 'cantidad': len(numeros),
                'faltantes': faltantes, 'duplicados': sorted(duplicados),
                'contador': contador, 'ok': ok,
            })
    return sorted(filas, key=lambda f: (f['empresa_id'], f['tipo_label'], f['punto']))


# ---------------------------------------------------------------------------
# Series NO FISCALES de venta (Plan 075)
# ---------------------------------------------------------------------------
# La serie FISCAL la gobierna ARCA: el número sale de la respuesta del CAE y el sistema
# la acompaña. Estas dos no tienen ninguna autoridad externa que las valide, así que su
# correlatividad depende enteramente de nosotros, y por eso se toman con bloqueo.
#
# El punto de emisión es `sucursal_id`, la sucursal que emite el comprobante (definición
# del usuario). PRE y NCI llevan series INDEPENDIENTES: así cada una se audita por
# (empresa, tipo, punto) igual que el resto, sin ninguna excepción que recordar.

def siguiente_numero_pre(empresa, sucursal_id):
    """Próximo número de Presupuesto / PRE (no fiscal) para esa sucursal."""
    return siguiente_numero(empresa, sucursal_id, ContadorDocumento.VENTA_PRE)


def siguiente_numero_nci(empresa, sucursal_id):
    """Próximo número de Nota de Crédito Interna (no fiscal) para esa sucursal."""
    return siguiente_numero(empresa, sucursal_id, ContadorDocumento.VENTA_NCI)
