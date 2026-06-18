from django import forms
from django.contrib.auth.models import User


class RegisterForm(forms.Form):
    """
    Form de registro simplificado para a API JSON.
    Aceita username, email e password (sem confirmação dupla),
    com validações equivalentes às do Django.
    """
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(min_length=8)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if password.isdigit():
            raise forms.ValidationError('A senha não pode conter apenas números.')
        return password

    def save(self):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['username'],
            email=data.get('email', ''),
            password=data['password'],
        )
        return user
