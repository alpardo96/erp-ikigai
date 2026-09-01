from django.contrib import admin

from .models import ContadorDocumento


@admin.register(ContadorDocumento)
class ContadorDocumentoAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'punto', 'tipo_documento', 'ultimo_numero')
    list_filter = ('empresa', 'tipo_documento', 'punto')
    search_fields = ('empresa__nombre',)
