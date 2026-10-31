from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()

# Enregistrement de tous les ViewSets
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'dossiers', DossierViewSet, basename='dossier')
router.register(r'fichiers', FichierViewSet, basename='fichier')
router.register(r'audiences', AudienceViewSet, basename='audience')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    # Routes automatiques du routeur DRF (clients, dossiers, fichiers, audiences, notifications)
    path('', include(router.urls)),

    # Authentification, Profil & Gestion des utilisateurs
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/logout/', LogoutJWTView.as_view(), name='logout'),
    path('users/', UserListView.as_view(), name='user-list'),
]