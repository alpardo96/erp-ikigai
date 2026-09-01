"""Restricción del cajero de mostrador (Plan 077 §G).

EL CAJERO OPERA TODO DESDE SU CAJA MOSTRADOR: cobra con el recibo que sale de esa pantalla
y rinde al cerrarla. No emite recibos ni órdenes de pago de Tesorería, ni entra a la caja de
Tesorería ni a la bandeja donde se recibe lo que él mismo rinde.

EL BLOQUEO VA EN LAS VISTAS, NO SÓLO EN EL MENÚ. Esconder un link no es un permiso: la URL
sigue estando ahí para quien la escriba o la tenga en favoritos.

Es una RESTRICCIÓN y no un permiso, y por eso `es_cajero_mostrador` arranca en `False`: así
nadie pierde accesos al aplicar el cambio y sólo queda acotado quien se marque.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

MENSAJE = ("Tu usuario opera únicamente su Caja Mostrador. Las cobranzas las hacés con el "
           "botón «Emitir Recibo» de esa pantalla, y rendís al cerrarla.")


def es_cajero_restringido(usuario):
    """True si el usuario está acotado a su caja. El admin de sistema nunca lo está."""
    perfil = getattr(usuario, 'perfil', None)
    if not perfil or perfil.es_admin_sistema or usuario.is_superuser:
        return False
    return bool(perfil.es_cajero_mostrador)


def bloquear_cajero(vista):
    """Decorador para las vistas de Tesorería que el cajero no debe operar."""

    @wraps(vista)
    def _envuelta(request, *args, **kwargs):
        if es_cajero_restringido(request.user):
            messages.error(request, MENSAJE)
            return redirect('caja_mostrador_index')
        return vista(request, *args, **kwargs)

    return _envuelta


class SinCajeroMostradorMixin:
    """Mismo bloqueo para las vistas basadas en clase."""

    def dispatch(self, request, *args, **kwargs):
        if es_cajero_restringido(request.user):
            messages.error(request, MENSAJE)
            return redirect('caja_mostrador_index')
        return super().dispatch(request, *args, **kwargs)
