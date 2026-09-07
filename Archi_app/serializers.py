from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Dossier, Fichier, PermissionDossier, PermissionFichier

from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth import get_user_model

User = get_user_model()

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
            ('invite', 'Invité')
        ]),
        default='utilisateur'
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'utilisateur')
        )
        return user

User = get_user_model()

# Serializer simplifié pour afficher l'utilisateur partagé
class UserShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    role = serializers.ChoiceField(choices=getattr(User, 'ROLE_CHOICES', [
        ('admin', 'Administrateur'),
        ('utilisateur', 'Utilisateur'),
        ('invite', 'Invité')
    ]), default='utilisateur')

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data.get('role', 'utilisateur')
        )
        return user


User = get_user_model()

class UserCurrentSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
        read_only_fields = ['id', 'role']    


# Serializer pour afficher le profil public de l'utilisateur avec son rôle
class UserShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']

# Serializers pour afficher les permissions accordées
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


# Serializer Fichier enrichi
class FichierSerializer(serializers.ModelSerializer):
    proprietaire = serializers.ReadOnlyField(source='proprietaire.username')
    permissions_partage = PermissionFichierSerializer(many=True, read_only=True)
    mon_niveau_acces = serializers.SerializerMethodField()

    class Meta:
        model = Fichier
        fields = [
            'id', 'nom_original', 'fichier', 'taille', 
            'mime_type', 'dossier', 'proprietaire', 
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


# Serializer Dossier enrichi
class DossierSerializer(serializers.ModelSerializer):
    proprietaire = serializers.ReadOnlyField(source='proprietaire.username')
    permissions_partage = PermissionDossierSerializer(many=True, read_only=True)
    sous_dossiers = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    fichiers = FichierSerializer(many=True, read_only=True)

    class Meta:
        model = Dossier
        fields = [
            'id', 'nom', 'parent', 'proprietaire', 
            'permissions_partage', 'sous_dossiers', 'fichiers', 'created_at'
        ]