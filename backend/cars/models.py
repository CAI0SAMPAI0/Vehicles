from django.db import models
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache


class Brand(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    
    def __str__(self) -> str:
        return self.name

class Car(models.Model):
    id = models.AutoField(primary_key=True) # id único e automático
    model = models.CharField(max_length=200) # tamanho/caracteres máximos
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='car_brand') # protect para proteger de remover tudo
    factory_year = models.IntegerField(blank=True, null=True) # campo não é obrigatório
    model_year = models.IntegerField(blank=True, null=True)
    plate = models.CharField(max_length=10, blank=True, null= True)
    value = models.FloatField(blank=True, null=True)
    photo = models.ImageField(upload_to='cars/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    
    def __str__(self) -> str:
        return self.model # fazendo mostrar o nome do carro ao invés do padrão feio do django
    
class CarInventory(models.Model):
    cars_count = models.IntegerField()
    cars_value = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.cars_count} - {self.cars_value}'


@receiver([post_save, post_delete], sender=Car)
def clear_cache_before_change(sender, instance, **kwargs):
    try:
        cache.clear()
    except Exception as e:
        print(f"Aviso: Não foi possível limpar o cache (Redis): {e}")