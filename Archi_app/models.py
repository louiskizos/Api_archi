import os
import uuid
import magic
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model



# models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Administrateur'),
        ('utilisateur', 'Utilisateur'),
        ('invite', 'Invité'),
        ('comptable', 'Comptable'),
        ('rh', 'Ressources Humaines'),
        ('communication', 'Communication'),
        ('avocat', 'Avocat'),
        ('programme', 'Programme'),
        ('secretaire', 'Secrétaire exécutif'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='utilisateur')

User = get_user_model()

def upload_to_user_directory(instance, filename):
    
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('uploads', f"user_{instance.proprietaire.id}", filename)


class Dossier(models.Model):
    nom = models.CharField(max_length=255)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True, related_name='sous_dossiers'
    )
    proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dossiers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('nom', 'parent', 'proprietaire')
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} (Propriétaire: {self.proprietaire.username})"


class Fichier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom_original = models.CharField(max_length=255)
    fichier = models.FileField(upload_to=upload_to_user_directory)
    taille = models.BigIntegerField(editable=False) # Taille en octets
    mime_type = models.CharField(max_length=100, editable=False)
    
    dossier = models.ForeignKey(
        Dossier, on_delete=models.CASCADE, null=True, blank=True, related_name='fichiers'
    )
    proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichiers')
    
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.nom_original

    def clean(self):
        """ Validation stricte de sécurité avant sauvegarde """
        if self.fichier:
            # 1. Vérification de la taille
            if self.fichier.size > getattr(settings, 'MAX_UPLOAD_SIZE', 20 * 1024 * 1024):
                raise ValidationError("La taille du fichier dépasse la limite autorisée (20 Mo).")

    def save(self, *args, **kwargs):
        if not self.pk or self._state.adding:
            # Capturer la taille du fichier
            self.taille = self.fichier.size
            self.nom_original = self.fichier.name
            
            # Détection du vrai type MIME
            self.fichier.open()
            mime = magic.from_buffer(self.fichier.read(2048), mime=True)
            self.mime_type = mime

            # Liste noire d'extensions exécutables dangereuses
            ext_interdites = ['.exe', '.php', '.sh', '.py', '.js', '.phtml', '.bat']
            ext = os.path.splitext(self.nom_original)[1].lower()
            if ext in ext_interdites:
                raise ValidationError(f"L'extension {ext} n'est pas autorisée par mesure de sécurité.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """ Supprimer physiquement le fichier du disque lors de la suppression en BDD """
        if self.fichier and os.path.isfile(self.fichier.path):
            os.remove(self.fichier.path)
        super().delete(*args, **kwargs)



User = get_user_model()

NIVEAU_ACCES = (
    ('lecture', 'Lecture seule'),
    ('ecriture', 'Lecture et Modification'),
)

class PermissionDossier(models.Model):
    dossier = models.ForeignKey('Dossier', on_delete=models.CASCADE, related_name='permissions_partage')
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dossiers_partages')
    niveau_acces = models.CharField(max_length=10, choices=NIVEAU_ACCES, default='lecture')

    class Meta:
        unique_together = ('dossier', 'utilisateur')


class PermissionFichier(models.Model):
    fichier = models.ForeignKey('Fichier', on_delete=models.CASCADE, related_name='permissions_partage')
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichiers_partages')
    niveau_acces = models.CharField(max_length=10, choices=NIVEAU_ACCES, default='lecture')

    class Meta:
        unique_together = ('fichier', 'utilisateur')