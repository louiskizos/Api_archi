import os
import uuid
import magic
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.conf import settings

# ==========================================
# 1. GESTION DES UTILISATEURS ET RÔLES
# ==========================================
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
    telephone = models.CharField(max_length=20, blank=True, null=True)


def upload_to_user_directory(instance, filename):
    ext = filename.split('.')[-1]
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    return os.path.join('uploads', f"user_{instance.proprietaire.id}", new_filename)


# ==========================================
# 2. GESTION DES CLIENTS
# ==========================================
class Client(models.Model):
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom}"


# ==========================================
# 3. DOSSIER SYSTÈME (Stockage technique)
# ==========================================
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
        verbose_name = "Dossier Système"
        verbose_name_plural = "Dossiers Systèmes"

    def __str__(self):
        return f"{self.nom} (Propriétaire: {self.proprietaire.username})"


# ==========================================
# 4. DOSSIER JURIDIQUE (Métier LegalTech)
# ==========================================
class Dossier_juridique(models.Model):
    class Statut(models.TextChoices):
        EN_COURS = 'EN_COURS', 'En cours'
        JUGE = 'JUGE', 'Jugé'
        ARCHIVE = 'ARCHIVE', 'Archivé'

    nom = models.CharField(max_length=255, help_text="Nom ou référence du dossier juridique")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='dossiers_juridiques', null=True, blank=True)
    type_affaire = models.CharField(max_length=100, blank=True, null=True, help_text="Ex: Droit civil, Pénal...")
    tribunal = models.CharField(max_length=150, blank=True, null=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS)
    
    proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dossiers_juridiques')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dossier Juridique"
        verbose_name_plural = "Dossiers Juridiques"
        ordering = ['nom']

    def __str__(self):
        client_str = f" - Client: {self.client}" if self.client else ""
        return f"[Juridique] {self.nom}{client_str} (Propriétaire: {self.proprietaire.username})"


# ==========================================
# 5. GESTION DES FICHIERS & SÉCURITÉ
# ==========================================
class Fichier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom_original = models.CharField(max_length=255)
    fichier = models.FileField(upload_to=upload_to_user_directory)
    taille = models.BigIntegerField(editable=False)  # Taille en octets
    mime_type = models.CharField(max_length=100, editable=False)
    
    # Lié au dossier système pour l'arborescence des fichiers
    dossier = models.ForeignKey(
        Dossier, on_delete=models.CASCADE, null=True, blank=True, related_name='fichiers'
    )
    # Optionnel: On peut aussi lier directement un fichier à un dossier juridique
    dossier_juridique = models.ForeignKey(
        Dossier_juridique, on_delete=models.CASCADE, null=True, blank=True, related_name='fichiers_juridiques'
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
        """Validation stricte de sécurité avant sauvegarde"""
        if self.fichier:
            # 1. Vérification de la taille (20 Mo par défaut)
            max_size = getattr(settings, 'MAX_UPLOAD_SIZE', 20 * 1024 * 1024)
            if self.fichier.size > max_size:
                raise ValidationError("La taille du fichier dépasse la limite autorisée (20 Mo).")

    def save(self, *args, **kwargs):
        if not self.pk or self._state.adding:
            self.taille = self.fichier.size
            self.nom_original = self.fichier.name
            
            # Détection du vrai type MIME via python-magic
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
        """Supprimer physiquement le fichier du disque lors de la suppression en BDD"""
        if self.fichier and os.path.isfile(self.fichier.path):
            os.remove(self.fichier.path)
        super().delete(*args, **kwargs)


# ==========================================
# 6. PERMISSIONS DE PARTAGE
# ==========================================
NIVEAU_ACCES = (
    ('lecture', 'Lecture seule'),
    ('ecriture', 'Lecture et Modification'),
)

class PermissionDossier(models.Model):
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name='permissions_partage')
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dossiers_partages')
    niveau_acces = models.CharField(max_length=10, choices=NIVEAU_ACCES, default='lecture')

    class Meta:
        unique_together = ('dossier', 'utilisateur')


class PermissionFichier(models.Model):
    fichier = models.ForeignKey(Fichier, on_delete=models.CASCADE, related_name='permissions_partage')
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fichiers_partages')
    niveau_acces = models.CharField(max_length=10, choices=NIVEAU_ACCES, default='lecture')

    class Meta:
        unique_together = ('fichier', 'utilisateur')


# ==========================================
# 7. GESTION DES AUDIENCES ET CALENDRIER
# ==========================================
class Audience(models.Model):
    # Les audiences sont rattachées logiquement aux dossiers juridiques
    dossier_juridique = models.ForeignKey(Dossier_juridique, on_delete=models.CASCADE, related_name='audiences')
    date_audience = models.DateTimeField()
    tribunal = models.CharField(max_length=150)
    observations = models.TextField(blank=True, null=True)
    
    rappel_envoye = models.BooleanField(default=False, help_text="Indique si le rappel automatique a été envoyé")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Audience"
        verbose_name_plural = "Audiences"
        ordering = ['date_audience']

    def __str__(self):
        date_str = self.date_audience.strftime('%d/%m/%Y %H:%M') if self.date_audience else "Date non définie"
        return f"Audience du {date_str} - Dossier: {self.dossier_juridique.nom}"


# ==========================================
# 8. NOTIFICATIONS ET RAPPELS
# ==========================================
class Notification(models.Model):
    class TypeNotification(models.TextChoices):
        AUDIENCE_RAPPEL = 'AUDIENCE_RAPPEL', 'Rappel d\'audience'
        DOCUMENT_AJOUTE = 'DOCUMENT_AJOUTE', 'Document ajouté'
        DOSSIER_MODIFIE = 'DOSSIER_MODIFIE', 'Dossier modifié'

    destinataire = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    titre = models.CharField(max_length=200)
    message = models.TextField()
    type_notification = models.CharField(max_length=30, choices=TypeNotification.choices)
    est_lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.get_type_notification_display()} pour {self.destinataire.username}"