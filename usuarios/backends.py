from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

class CaseInsensitiveModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        try:
            case_insensitive_username_field = '{}__iexact'.format(UserModel.USERNAME_FIELD)
            user = UserModel._default_manager.get(**{case_insensitive_username_field: username})
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce the timing
            # difference between an existing and a nonexistent user.
            UserModel().set_password(password)
        else:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        return None

    def get_all_permissions(self, user_obj, obj=None):
        """
        Calcula todos los permisos (directos + heredados de grupos) y RESTA
        los que estén explícitamente registrados en PermisoDenegado.
        """
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()

        # Obtenemos los permisos nativos de Django (user_permissions + group_permissions)
        perms = super().get_all_permissions(user_obj, obj)

        # Si el usuario tiene permisos denegados registrados, los restamos
        denied_ids = list(user_obj.permisos_denegados.values_list('permiso_id', flat=True))
        if denied_ids:
            from django.contrib.auth.models import Permission
            denied_perms = Permission.objects.filter(id__in=denied_ids).values_list('content_type__app_label', 'codename')
            denied_set = {f"{ct}.{name}" for ct, name in denied_perms}
            perms = perms - denied_set

        return perms
