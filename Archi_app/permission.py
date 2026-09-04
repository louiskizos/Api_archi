from rest_framework import permissions
from .models import PermissionFichier, PermissionDossier

class IsOwnerOrSharedAccess(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # 1. Le propriétaire a tous les droits
        if obj.proprietaire == request.user:
            return True

        # 2. Déterminer si la requête est une modification ou une simple lecture
        est_lecture = request.method in permissions.SAFE_METHODS

        # Vérification sur un Fichier
        if hasattr(obj, 'permissions_partage'):
            perm = obj.permissions_partage.filter(utilisateur=request.user).first()
            if perm:
                if est_lecture:
                    return True  # 'lecture' ou 'ecriture' autorisé
                return perm.niveau_acces == 'ecriture' # Seule 'ecriture' autorisée pour modifier

        return False