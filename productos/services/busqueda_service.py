from django.db.models import Q, Case, When, Value, IntegerField, DecimalField, Exists, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce
from productos.models import Producto, Subproducto, StockSucursal


def construir_filtro_busqueda_producto(q, empresa_id, solo_trazabilidad=False, excluir_subprod=False, proveedor_id=None, campo='todos'):
    """
    Construye la consulta Q y la expresión de ordenamiento por relevancia para productos.
    Soporta búsqueda por campo específico ('detalle', 'rubro', 'calibre', 'cod_prov', 'proveedor', 'id')
    o búsqueda general ('todos') a través de múltiples atributos concatenados.
    
    Optimiza la consulta precargando relaciones y calculando el stock global en la misma query.
    Retorna: (queryset_filtrado, tiene_orden_relevancia)
    """
    empresa_filtros = Q(empresa_id=empresa_id, activo=True)
    if excluir_subprod:
        empresa_filtros &= Q(subprod=False)
    if proveedor_id:
        empresa_filtros &= Q(proveedor_id=proveedor_id)

    # Subconsulta agregada para el stock global consolidado (evita N+1 queries en el renderizado)
    subq_stock = StockSucursal.objects.filter(
        producto_id=OuterRef('pk')
    ).values('producto_id').annotate(total=Sum('cantidad')).values('total')

    qs = Producto.objects.filter(empresa_filtros).select_related(
        'proveedor', 'marca', 'rubro', 'familia'
    ).annotate(
        stock_total_calc=Coalesce(
            Subquery(subq_stock, output_field=DecimalField(max_digits=15, decimal_places=2)),
            Value(0, output_field=DecimalField(max_digits=15, decimal_places=2))
        )
    )

    if solo_trazabilidad:
        subproductos_con_prod = Subproducto.objects.filter(
            empresa_id=empresa_id,
            producto_id=OuterRef('pk')
        )
        qs = qs.annotate(en_trazabilidad=Exists(subproductos_con_prod)).filter(en_trazabilidad=True)

    q_clean = (q or '').strip()
    if not q_clean:
        return qs.order_by('detalle'), False

    # Filtros por campo específico si el usuario lo seleccionó
    campo_clean = (campo or 'todos').lower().strip()
    if campo_clean == 'detalle':
        return qs.filter(detalle__icontains=q_clean).order_by('detalle'), False
    elif campo_clean == 'rubro':
        return qs.filter(rubro__detalle__icontains=q_clean).order_by('rubro__detalle', 'detalle'), False
    elif campo_clean == 'calibre':
        return qs.filter(unidad_venta__icontains=q_clean).order_by('detalle'), False
    elif campo_clean == 'cod_prov':
        return qs.filter(cod_prov__icontains=q_clean).order_by('detalle'), False
    elif campo_clean == 'proveedor':
        return qs.filter(proveedor__razon_social__icontains=q_clean).order_by('detalle'), False
    elif campo_clean == 'id':
        if q_clean.isdigit():
            return qs.filter(id=int(q_clean)), False
        return qs.none(), False

    # Búsqueda general ('todos'): multi-término AND a través de todos los atributos
    terminos = [t for t in q_clean.split() if t]
    if not terminos:
        return qs.order_by('detalle'), False

    filtro_terminos = Q()
    for term in terminos:
        term_q = (
            Q(detalle__icontains=term) |
            Q(cod_fab__icontains=term) |
            Q(cod_prov__icontains=term) |
            Q(codigo_anterior__icontains=term) |
            Q(marca__detalle__icontains=term) |
            Q(rubro__detalle__icontains=term) |
            Q(familia__detalle__icontains=term) |
            Q(unidad_venta__icontains=term) |
            Q(proveedor__razon_social__icontains=term)
        )
        if term.isdigit():
            term_q |= Q(id=int(term))
        filtro_terminos &= term_q

    qs = qs.filter(filtro_terminos)

    # Ordenamiento por relevancia según precisión del match
    whens = []
    if q_clean.isdigit():
        whens.append(When(id=int(q_clean), then=Value(1)))

    whens.append(When(Q(cod_fab__iexact=q_clean) | Q(cod_prov__iexact=q_clean) | Q(codigo_anterior__iexact=q_clean), then=Value(2)))
    whens.append(When(detalle__istartswith=q_clean, then=Value(3)))
    whens.append(When(rubro__detalle__istartswith=q_clean, then=Value(4)))
    whens.append(When(detalle__icontains=q_clean, then=Value(5)))
    whens.append(When(rubro__detalle__icontains=q_clean, then=Value(6)))
    whens.append(When(marca__detalle__istartswith=q_clean, then=Value(7)))

    prioridad_expr = Case(
        *whens,
        default=Value(8),
        output_field=IntegerField()
    )

    qs = qs.annotate(_relevancia=prioridad_expr).order_by('_relevancia', 'detalle')
    return qs, True


def buscar_productos_inteligente(q, empresa_id, solo_trazabilidad=False, excluir_subprod=False, proveedor_id=None, campo='todos', limit=100):
    """
    Ejecuta la búsqueda inteligente de productos y retorna una lista o queryset acotado al límite solicitado.
    """
    qs, _ = construir_filtro_busqueda_producto(
        q=q,
        empresa_id=empresa_id,
        solo_trazabilidad=solo_trazabilidad,
        excluir_subprod=excluir_subprod,
        proveedor_id=proveedor_id,
        campo=campo
    )
    if limit:
        return qs[:limit]
    return qs
