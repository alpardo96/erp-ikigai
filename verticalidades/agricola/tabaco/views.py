from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def agro_index(request):
    """Hub principal con accesos por tarjeta y resumen operativo de Acopio de Tabaco."""
    return render(request, 'agricola/index.html')
