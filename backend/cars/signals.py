import threading
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from cars.models import Car, CarInventory
from openai_api.client import get_car_ai_bio, get_car_ai_category
from cars.utils import fetch_and_save_car_photo


def car_invetory_update():
    cars_count = Car.objects.all().count()
    cars_value = Car.objects.aggregate(
        total_value=Sum('value')
    )['total_value']
    CarInventory.objects.create(
        cars_count=cars_count,
        cars_value=cars_value
    )


def _fill_ai_fields_async(car_id: int):
    """
    Preenche bio e categoria de um carro via IA de forma assíncrona.
    Roda em thread daemon — não bloqueia o request HTTP.
    Usa update_fields para evitar loop de signals.
    """
    try:
        car = Car.objects.select_related('brand').get(pk=car_id)
    except Car.DoesNotExist:
        return

    fields_to_update = []

    if not car.bio:
        try:
            car.bio = get_car_ai_bio(car.model, car.brand, car.model_year)
            fields_to_update.append('bio')
        except Exception as e:
            print(f"[AI] Erro ao gerar bio para carro {car_id}: {e}", flush=True)

    if not car.categoria:
        try:
            car.categoria = get_car_ai_category(car.brand, car.model, car.model_year)
            fields_to_update.append('categoria')
        except Exception as e:
            print(f"[AI] Erro ao classificar categoria para carro {car_id}: {e}", flush=True)

    if fields_to_update:
        # update_fields evita disparar o pre_save novamente (sem loop)
        car.save(update_fields=fields_to_update)
        print(f"[AI] Campos {fields_to_update} atualizados para carro {car_id}", flush=True)


# pre_save foi esvaziado — a IA agora é 100% assíncrona no post_save.
# Mantemos o receptor vazio por compatibilidade caso futuras extensões precisem dele.
@receiver(pre_save, sender=Car)
def car_pre_save(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=Car)
def car_post_save(sender, instance, created, **kwargs):
    car_invetory_update()

    # Só dispara IA e foto quando houver campos faltando (evita re-trigger de update_fields)
    needs_ai = not instance.bio or not instance.categoria
    needs_photo = not instance.photo

    if needs_ai:
        thread = threading.Thread(target=_fill_ai_fields_async, args=(instance.id,))
        thread.daemon = True
        thread.start()

    if needs_photo:
        thread = threading.Thread(target=fetch_and_save_car_photo, args=(instance.id,))
        thread.daemon = True
        thread.start()


@receiver(post_delete, sender=Car)
def car_post_delete(sender, instance, **kwargs):
    car_invetory_update()
