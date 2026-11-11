from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Permet à un utilisateur de se connecter en utilisant son adresse email à la place du username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get('email')
        if email is None:
            return None
        
        try:
            # Recherche de l'utilisateur par son e-mail (insensible à la casse)
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).order_by('id').first()

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None