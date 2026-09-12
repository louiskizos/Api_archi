from django.urls import path, include
from rest_framework.routers import DefaultRouter


from .views import *

router = DefaultRouter()
router.register(r'dossiers', DossierViewSet, basename='dossier')
router.register(r'fichiers', FichierViewSet, basename='fichier')

urlpatterns = [
    # Gestion des fichiers et dossiers
    path('', include(router.urls)),

    # Authentification & Création de compte
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/logout/', LogoutJWTView.as_view(), name='logout'),
    path('users/', UserListView.as_view(), name='user-list'),
    
]