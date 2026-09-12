from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Dossier, Fichier, PermissionDossier, PermissionFichier
from .serializers import *
from .permission import IsOwnerOrSharedAccess
from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()



User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]  
    serializer_class = RegisterSerializer


class LogoutJWTView(APIView):
    permission_classes = [IsAuthenticated]

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

    @action(detail=True, methods=['post'], url_path='revoker-partage')
    def revoker_partage(self, request, pk=None):
        """
        POST /api/dossiers/{id}/revoker-partage/
        Body: {"utilisateur_id": 2}
        """
        dossier = self.get_object()

        if dossier.proprietaire != request.user:
            return Response({'error': 'Action non autorisée.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        PermissionDossier.objects.filter(dossier=dossier, utilisateur_id=user_id).delete()

        return Response({'status': 'Permission révoquée avec succès.'})


class CurrentUserView(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserCurrentSerializer(request.user)
        return Response(serializer.data)


class UserListView(generics.ListAPIView):
    
    queryset = User.objects.all().order_by('id')
    serializer_class = UserCurrentSerializer
    permission_classes = [permissions.IsAuthenticated]

class FichierViewSet(viewsets.ModelViewSet):

    
    serializer_class = FichierSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrSharedAccess]

    def get_queryset(self):
        user = self.request.user
        return Fichier.objects.filter(
            Q(proprietaire=user) | Q(permissions_partage__utilisateur=user)
        ).distinct()

    def perform_create(self, serializer):
        serializer.save(proprietaire=self.request.user)

    @action(detail=True, methods=['post'], url_path='partager')
    def partager(self, request, pk=None):
        """
        POST /api/fichiers/{id}/partager/
        Body: {"utilisateur_id": 2, "niveau_acces": "ecriture"}
        """
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

    @action(detail=True, methods=['post'], url_path='revoker-partage')
    def revoker_partage(self, request, pk=None):
        """
        POST /api/fichiers/{id}/revoker-partage/
        Body: {"utilisateur_id": 2}
        """
        fichier = self.get_object()

        if fichier.proprietaire != request.user:
            return Response({'error': 'Action non autorisée.'}, status=status.HTTP_403_FORBIDDEN)

        user_id = request.data.get('utilisateur_id')
        PermissionFichier.objects.filter(fichier=fichier, utilisateur_id=user_id).delete()

        return Response({'status': 'Permission révoquée avec succès.'})