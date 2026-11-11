from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model
from .models import *
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


User = get_user_model()


# ==========================================
# 1. UTILISATEURS & AUTHENTIFICATION
# ==========================================
class RegisterSerializer(serializers.ModelSerializer):
    username = serializers.CharField(
        required=True,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            message="Un utilisateur avec ce nom d'utilisateur existe déjà."
        )]
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        validators=[UniqueValidator(
            queryset=User.objects.all(),
            message="Un utilisateur avec cet e-mail existe déjà."
        )]
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    role = serializers.ChoiceField(
        choices=getattr(User, 'ROLE_CHOICES', [
            ('admin', 'Administrateur'),
            ('utilisateur', 'Utilisateur'),
            ('invite', 'Invité'),
            ('comptable', 'Comptable'),
            ('rh', 'Ressources Humaines'),
            ('communication', 'Communication'),
            ('avocat', 'Avocat'),
            ('programme', 'Programme'),
            ('secretaire', 'Secrétaire exécutif'),
        ]),
        default='utilisateur'
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'telephone']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'utilisateur'),
            telephone=validated_data.get('telephone', '')
        )
        return user



class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Personnalise SimpleJWT pour utiliser 'email' au lieu de 'username' comme identifiant.
    """
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            attrs["username"] = email
            
        return super().validate(attrs)


class UserCurrentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'telephone']
        read_only_fields = ['id', 'role']    


class UserShareSerializer(serializers.ModelSerializer):
    """Serializer public pour afficher les utilisateurs lors des partages."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']


# ==========================================
# 2. CLIENTS
# ==========================================
class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'


# ==========================================
# 3. PERMISSIONS
# ==========================================
class PermissionFichierSerializer(serializers.ModelSerializer):
    utilisateur = UserShareSerializer(read_only=True)

    class Meta:
        model = PermissionFichier
        fields = ['id', 'utilisateur', 'niveau_acces']


class PermissionDossierSerializer(serializers.ModelSerializer):
    utilisateur = UserShareSerializer(read_only=True)

    class Meta:
        model = PermissionDossier
        fields = ['id', 'utilisateur', 'niveau_acces']


# ==========================================
# 4. FICHIERS & DOSSIERS SYSTÈME
# ==========================================
class FichierSerializer(serializers.ModelSerializer):
    proprietaire = serializers.ReadOnlyField(source='proprietaire.username')
    permissions_partage = PermissionFichierSerializer(many=True, read_only=True)
    mon_niveau_acces = serializers.SerializerMethodField()

    class Meta:
        model = Fichier
        fields = [
            'id', 'nom_original', 'fichier', 'taille', 
            'mime_type', 'dossier', 'dossier_juridique', 'proprietaire', 
            'is_public', 'permissions_partage', 'mon_niveau_acces',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'taille', 'mime_type', 'proprietaire', 'nom_original']

    def get_mon_niveau_acces(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        if obj.proprietaire == request.user:
            return 'proprietaire'
        perm = obj.permissions_partage.filter(utilisateur=request.user).first()
        return perm.niveau_acces if perm else None


class DossierSerializer(serializers.ModelSerializer):
    proprietaire = serializers.ReadOnlyField(source='proprietaire.username')
    permissions_partage = PermissionDossierSerializer(many=True, read_only=True)
    sous_dossiers = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    fichiers = FichierSerializer(many=True, read_only=True)

    class Meta:
        model = Dossier
        fields = [
            'id', 'nom', 'parent', 'proprietaire', 
            'permissions_partage', 'sous_dossiers', 'fichiers', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['proprietaire', 'created_at', 'updated_at']


# ==========================================
# 5. DOSSIERS JURIDIQUES (Métier LegalTech)
# ==========================================
class DossierJuridiqueSerializer(serializers.ModelSerializer):
    proprietaire = serializers.ReadOnlyField(source='proprietaire.username')
    client_detail = ClientSerializer(source='client', read_only=True)
    fichiers_juridiques = FichierSerializer(many=True, read_only=True)

    class Meta:
        model = Dossier_juridique
        fields = [
            'id', 'nom', 'client', 'client_detail', 'type_affaire', 
            'tribunal', 'statut', 'proprietaire', 'fichiers_juridiques', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['proprietaire', 'created_at', 'updated_at']


# ==========================================
# 6. AUDIENCES & NOTIFICATIONS
# ==========================================
class AudienceSerializer(serializers.ModelSerializer):
    dossier_juridique_nom = serializers.ReadOnlyField(source='dossier_juridique.nom')

    class Meta:
        model = Audience
        fields = [
            'id', 'dossier_juridique', 'dossier_juridique_nom', 
            'date_audience', 'tribunal', 'observations', 
            'rappel_envoye', 'date_creation'
        ]
        read_only_fields = ['rappel_envoye', 'date_creation']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'destinataire', 'titre', 'message', 'type_notification', 'est_lue', 'date_creation']
        read_only_fields = ['destinataire', 'date_creation']