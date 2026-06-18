import secrets
from django.db import models
from django.contrib.auth.models import User


class AuthToken(models.Model):
    """
    Token de autenticação simples para o frontend SPA.
    Gerado no login e retornado ao cliente para ser armazenado no localStorage.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='auth_token')
    key = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Token de {self.user.username}'

    @classmethod
    def get_or_create_for_user(cls, user):
        """Retorna o token existente ou cria um novo para o usuário."""
        try:
            token = cls.objects.get(user=user)
        except cls.DoesNotExist:
            token = cls.objects.create(
                user=user,
                key=secrets.token_hex(32),
            )
        return token.key
