from django.apps import AppConfig


class TabacoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'verticalidades.agricola.tabaco'
    verbose_name = 'Agrícola (Tabaco)'

    def ready(self):
        """Anuncia los orígenes que esta verticalidad aporta al core (Plan 080).

        El import va acá adentro y no arriba porque en el momento en que se define la clase los
        modelos todavía no están cargados.
        """
        from . import registros
        registros.registrar_todo()
