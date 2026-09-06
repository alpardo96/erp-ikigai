"""Rutas de la verticalidad Agrícola.

POR QUÉ EXISTE ESTE ARCHIVO
El auto-descubrimiento de `config/urls.py` recorre `verticalidades/<app>/` e incluye la app sólo
si encuentra un `urls.py` **en ese primer nivel**. Como `agricola` es un contenedor de sub-apps
(`tabaco`, `granos`) y no una app en sí misma, sin este archivo ninguna de sus rutas llegaba a
Django.

Se resuelve acá, del lado de la verticalidad, sin tocar `config/urls.py`: el mecanismo del core
ya sirve, lo que faltaba era el punto de entrada.

Cada sub-app se incluye con `try/except` para que una sub-app a medio hacer no tumbe a las demás
ni al ERP (Plan 075).
"""
from django.urls import include, path

urlpatterns = []

for _subapp in ('tabaco', 'granos'):
    try:
        urlpatterns.append(path('', include(f'verticalidades.agricola.{_subapp}.urls')))
    except ModuleNotFoundError:
        continue
