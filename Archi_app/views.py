from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework import serializers
from .models import *
from .serializers import *
from .permission import IsOwnerOrSharedAccess
from rest_framework_simplejwt.views import TokenObtainPairView

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
User = get_user_model()


# --- Serializers temporaires pour la doc si non définis dans serializers.py ---
class PartageRequestSerializer(serializers.Serializer):
    utilisateur_id = serializers.IntegerField(help_text="ID de l'utilisateur avec qui partager")
    niveau_acces = serializers.ChoiceField(choices=['lecture', 'ecriture'], default='lecture', help_text="Niveau d'accès accordé")

class RevokerPartageRequestSerializer(serializers.Serializer):
    utilisateur_id = serializers.IntegerField(help_text="ID de l'utilisateur dont on révoque l'accès")

class LogoutRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(help_text="Jeton de rafraîchissement (refresh token) JWT")
# ------------------------------------------------------------------------------


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]  
    serializer_class = RegisterSerializer

class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


class LogoutJWTView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutRequestSerializer,
        responses={205: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        description="Invalide le jeton de rafraîchissement (refresh token) pour déconnecter l'utilisateur."
    )
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if not refresh_token:
                return Response({"error": "Le jeton refresh est requis."}, status=status.HTTP_400_BAD_REQUEST)

            token = RefreshToken(refresh_token)
            token.blacklist()  

            return Response({"message": "Déconnexion réussie."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Jeton invalide ou expiré."}, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses={200: UserCurrentSerializer},
        description="Récupère les informations de l'utilisateur actuellement connecté."
    )
    def get(self, request):
        serializer = UserCurrentSerializer(request.user)
        return Response(serializer.data)


class UserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('id')
    serializer_class = UserCurrentSerializer
    permission_classes = [permissions.IsAuthenticated]


# ==========================================
# 1. CLIENTS VIEWS
# ==========================================
class ClientViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les fiches clients du cabinet.
    """
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]


# ==========================================
# 2. DOSSIERS SYSTÈME VIEWS (Stockage)
# ==========================================
class DossierViewSet(viewsets.ModelViewSet):
    serializer_class = DossierSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrSharedAccess]

    def get_queryset(self):
        user = self.request.user
        return Dossier.objects.filter(
            Q(proprietaire=user) | Q(permissions_partage__utilisateur=user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(proprietaire=self.request.user)

    @extend_schema(
        request=PartageRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        description="Partage un dossier système avec un autre utilisateur."
    )
    @action(detail=True, methods=['post'], url_path='partager')
    def partager(self, request, pk=None):
        dossier = self.get_object()

        if dossier.proprietaire != request.user:
            return Response({'error': 'Seul le propriétaire peut partager ce dossier.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        niveau_acces = request.data.get('niveau_acces', 'lecture')

        if niveau_acces not in ['lecture', 'ecriture']:
            return Response({'error': 'Niveau d\'accès invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        PermissionDossier.objects.update_or_create(
            dossier=dossier,
            utilisateur_id=user_id,
            defaults={'niveau_acces': niveau_acces}
        )

        return Response({
            'status': f'Dossier partagé avec succès en mode {niveau_acces}.'
        }, status=status.HTTP_200_OK)

    @extend_schema(
        request=RevokerPartageRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        description="Révoque l'accès d'un utilisateur à ce dossier système."
    )
    @action(detail=True, methods=['post'], url_path='revoker-partage')
    def revoker_partage(self, request, pk=None):
        dossier = self.get_object()

        if dossier.proprietaire != request.user:
            return Response({'error': 'Action non autorisée.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        PermissionDossier.objects.filter(dossier=dossier, utilisateur_id=user_id).delete()

        return Response({'status': 'Permission révoquée avec succès.'})


# ==========================================
# 3. DOSSIERS JURIDIQUES VIEWS (Métier)
# ==========================================
class DossierJuridiqueViewSet(viewsets.ModelViewSet):
    """
    API pour la gestion des dossiers juridiques du cabinet (affaires, tribunaux, clients).
    """
    serializer_class = DossierJuridiqueSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Dossier_juridique.objects.all()
        # Les avocats/utilisateurs voient leurs dossiers
        return Dossier_juridique.objects.filter(proprietaire=user)

    def perform_create(self, serializer):
        serializer.save(proprietaire=self.request.user)


# ==========================================
# 4. FICHIERS VIEWS
# ==========================================
class FichierViewSet(viewsets.ModelViewSet):
    serializer_class = FichierSerializer
   # permission_classes = [permissions.IsAuthenticated, IsOwnerOrSharedAccess]

    def get_queryset(self):
        user = self.request.user
        queryset = Fichier.objects.filter(
            Q(proprietaire=user) | Q(permissions_partage__utilisateur=user)
        ).distinct()

        # Filtrer par dossier système si spécifié dans l'URL (?dossier=ID)
        dossier_id = self.request.query_params.get('dossier')
        if dossier_id:
            queryset = queryset.filter(dossier_id=dossier_id)

        # Filtrer par dossier juridique si spécifié dans l'URL (?dossier_juridique=ID)
        dossier_juridique_id = self.request.query_params.get('dossier_juridique')
        if dossier_juridique_id:
            queryset = queryset.filter(dossier_juridique_id=dossier_juridique_id)

        return queryset

    def perform_create(self, serializer):
        serializer.save(proprietaire=self.request.user)

    @extend_schema(
        request=PartageRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        description="Partage un fichier avec un autre utilisateur."
    )
    @action(detail=True, methods=['post'], url_path='partager')
    def partager(self, request, pk=None):
        fichier = self.get_object()

        if fichier.proprietaire != request.user:
            return Response({'error': 'Seul le propriétaire peut partager ce fichier.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        niveau_acces = request.data.get('niveau_acces', 'lecture')

        if niveau_acces not in ['lecture', 'ecriture']:
            return Response({'error': 'Niveau d\'accès invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        perm, created = PermissionFichier.objects.update_or_create(
            fichier=fichier,
            utilisateur_id=user_id,
            defaults={'niveau_acces': niveau_acces}
        )

        return Response({
            'status': f'Fichier partagé avec succès en mode {niveau_acces}.'
        }, status=status.HTTP_200_OK)

    @extend_schema(
        request=RevokerPartageRequestSerializer,
        responses={200: OpenApiTypes.OBJECT, 403: OpenApiTypes.OBJECT},
        description="Révoque l'accès d'un utilisateur à ce fichier."
    )
    @action(detail=True, methods=['post'], url_path='revoker-partage')
    def revoker_partage(self, request, pk=None):
        fichier = self.get_object()

        if fichier.proprietaire != request.user:
            return Response({'error': 'Action non autorisée.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        PermissionFichier.objects.filter(fichier=fichier, utilisateur_id=user_id).delete()

        return Response({'status': 'Permission révoquée avec succès.'})

# ==========================================
# 5. AUDIENCES VIEWS
# ==========================================
class AudienceViewSet(viewsets.ModelViewSet):
    """
    API pour la planification et le suivi des audiences liées aux dossiers juridiques.
    """
    queryset = Audience.objects.all()
    serializer_class = AudienceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Audience.objects.all()
        # Filtrer par les audiences liées aux dossiers juridiques appartenant à l'utilisateur
        return Audience.objects.filter(dossier_juridique__proprietaire=user).distinct()


# ==========================================
# 6. NOTIFICATIONS VIEWS
# ==========================================
class NotificationViewSet(viewsets.ModelViewSet):
    """
    API pour gérer les notifications de l'utilisateur connecté (rappels d'audiences, etc.).
    """
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(destinataire=self.request.user)

    @action(detail=True, methods=['post'], url_path='marquer-comme-lue')
    def marquer_comme_lue(self, request, pk=None):
        """
        Action personnalisée pour marquer une notification spécifique comme lue.
        """
        notification = self.get_object()
        notification.est_lue = True
        notification.save()
        return Response({'status': 'Notification marquée comme lue.'}, status=status.HTTP_200_OK)