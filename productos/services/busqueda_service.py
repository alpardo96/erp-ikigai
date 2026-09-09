from django.db.models import Q, Case, When, Value, IntegerField, Exists, OuterRef
from productos.models import Producto, Subproducto


def construir_filtro_busqueda_producto(q, empresa_id, solo_trazabilidad=False, excluir_subprod=False, proveedor_id=None):
    """
    Construye la consulta Q y la expresión de ordenamiento por relevancia para productos.
    Permite buscar términos concatenados en cualquier orden (adelante, atrás, al medio)
    y a través de múltiples atributos (detalle, cod_fab, cod_prov, codigo_anterior, marca, rubro, familia, id).
    
    Retorna: (queryset_filtrado, tiene_orden_relevancia)
    """
    empresa_filtros = Q(empresa_id=empresa_id)
    if excluir_subprod:
        empresa_filtros &= Q(subprod=False)
    if proveedor_id:
        empresa_filtros &= Q(proveedor_id=proveedor_id)

    qs = Producto.objects.filter(empresa_filtros)

    if solo_trazabilidad:
        subproductos_con_prod = Subproducto.objects.filter(
            empresa_id=empresa_id,
            producto_id=OuterRef('pk')
        )
        qs = qs.annotate(en_trazabilidad=Exists(subproductos_con_prod)).filter(en_trazabilidad=True)

    q_clean = (q or '').strip()
    if not q_clean:
        return qs.order_by('detalle'), False

    terminos = [t for t in q_clean.split() if t]
    if not terminos:
        return qs.order_by('detalle'), False

    # Filtro multi-término AND: cada palabra ingresada debe encontrarse en al menos uno de los campos
    filtro_terminos = Q()
    for term in terminos:
        term_q = (
            Q(detalle__icontains=term) |
            Q(cod_fab__icontains=term) |
            Q(cod_prov__icontains=term) |
            Q(codigo_anterior__icontains=term) |
            Q(marca__detalle__icontains=term) |
            Q(rubro__detalle__icontains=term) |
            Q(familia__detalle__icontains=term)
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
    whens.append(When(detalle__icontains=q_clean, then=Value(4)))
    whens.append(When(marca__detalle__istartswith=q_clean, then=Value(5)))

    prioridad_expr = Case(
        *whens,
        default=Value(6),
        output_field=IntegerField()
    )

    qs = qs.annotate(_relevancia=prioridad_expr).order_by('_relevancia', 'detalle')
    return qs, True


def buscar_productos_inteligente(q, empresa_id, solo_trazabilidad=False, excluir_subprod=False, proveedor_id=None, limit=100):
    """
    Ejecuta la búsqueda inteligente de productos y retorna una lista o queryset acotado al límite solicitado.
    """
    qs, _ = construir_filtro_busqueda_producto(
        q=q,
        empresa_id=empresa_id,
        solo_trazabilidad=solo_trazabilidad,
        excluir_subprod=excluir_subprod,
        proveedor_id=proveedor_id
    )
    if limit:
        return qs[:limit]
    return qs
