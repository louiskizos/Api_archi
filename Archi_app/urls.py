from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import *

router = DefaultRouter()
router.register(r'dossiers', DossierViewSet, basename='dossier')
router.register(r'fichiers', FichierViewSet, basename='fichier')

urlpatterns = [
    # Gestion des fichiers et dossiers
    path('', include(router.urls)),

    # Authentification & Création de compte
    path('auth/register/', RegisterView.as_view(), name='auth_register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]