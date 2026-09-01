# Plan de Implementación - Mostrar Conceptos Adicionales en Detalle de Compra (> 0)

Este cambio propone agregar los conceptos faltantes (`No Gravado` y `Exento`) al desglose del modal de detalle de compras, mostrando tanto estos nuevos conceptos como los impuestos y percepciones existentes **únicamente si su valor es mayor a cero**, logrando que la visualización sea limpia y que a su vez cuadren los valores con el total cuando existan estos importes.

## User Review Required

> [!NOTE]
> Este cambio no altera la estructura de la base de datos ni los cálculos de los modelos, sino únicamente la visualización de los conceptos en la interfaz de usuario dentro del modal de detalles de compra (`compra_detalle_modal.html`).
>
> Los conceptos que se validarán para mostrarse únicamente si son mayores a 0 son:
> - No Gravado [Nuevo]
> - Exento [Nuevo]
> - IVA
> - Percepción IVA
> - Percepción IIBB
> - Percepción Ganancias
> - Percepción Municipal
> - SIRCREB
> - Recargo Bancario
> - Otros

## Proposed Changes

---

### Facturación (Módulo de Compras)

#### [MODIFY] [views.py](file:///d:/OneDrive/Escritorio/Proyectos%20Django/erp-ikigai-2/facturacion/views.py)
- Modificar la clase `CompraDetalleModalView` para incluir `no_gravado` y `exento` en el desglose de conceptos, manteniendo el filtro para que sólo se añadan a la lista si su valor es mayor a 0.

```python
class CompraDetalleModalView(LoginRequiredMixin, View):
    def get(self, request, compra_id):
        empresa_id = request.session.get('empresa_id')
        compra = get_object_or_404(Compra, pk=compra_id, empresa_id=empresa_id)
        
        # Desglose de impuestos/percepciones/conceptos (solo si son mayores a 0)
        impuestos = []
        if compra.no_gravado > 0: impuestos.append({'nombre': 'No Gravado', 'monto': compra.no_gravado})
        if compra.exento > 0: impuestos.append({'nombre': 'Exento', 'monto': compra.exento})
        if compra.iva > 0: impuestos.append({'nombre': 'IVA', 'monto': compra.iva})
        if compra.p_iva > 0: impuestos.append({'nombre': 'Perc. IVA', 'monto': compra.p_iva})
        if compra.p_iibb > 0: impuestos.append({'nombre': 'Perc. IIBB', 'monto': compra.p_iibb})
        if compra.p_gcia > 0: impuestos.append({'nombre': 'Perc. Gcia', 'monto': compra.p_gcia})
        if compra.p_mun > 0: impuestos.append({'nombre': 'Perc. Mun.', 'monto': compra.p_mun})
        if compra.p_sircreb > 0: impuestos.append({'nombre': 'SIRCREB', 'monto': compra.p_sircreb})
        if compra.p_recbc > 0: impuestos.append({'nombre': 'Rec. Bancario', 'monto': compra.p_recbc})
        if compra.otros > 0: impuestos.append({'nombre': 'Otros', 'monto': compra.otros})
        ...
```

## Verification Plan

### Manual Verification
1. Ingresar al ERP.
2. Ir a **Listado de Compras**.
3. Abrir el detalle de una compra que tenga cargados conceptos no gravados o exentos.
4. Verificar que se muestren en el cuadrito de totales.
5. Abrir el detalle de otra compra que no tenga dichos conceptos (o sea, que su valor sea 0).
6. Verificar que **no** se muestren en el cuadrito de totales, evitando ensuciar la pantalla.
7. Comprobar que en todos los casos la suma de los conceptos visibles (Neto Gravado + conceptos visibles) sea exactamente igual al **Total**.
