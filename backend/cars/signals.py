import threading
from django.db.models.signals import pre_save, post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from cars.models import Car, CarInventory
from openai_api.client import get_car_ai_bio, get_car_ai_category, get_car_ai_spec_sheet
from cars.utils import fetch_and_save_car_photo


def car_invetory_update():
    cars_count = Car.objects.all().count()
    cars_value = Car.objects.aggregate(
        total_value=Sum('value')
    )['total_value']
    if cars_value is None:
        cars_value = 0.0
    CarInventory.objects.create(
        cars_count=cars_count,
        cars_value=cars_value
    )


def _fill_ai_fields_async(car_id: int):
    """
    Preenche bio, categoria e ficha técnica de um carro via IA de forma assíncrona.
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

    if not car.ficha_tecnica:
        try:
            car.ficha_tecnica = get_car_ai_spec_sheet(car.brand.name, car.model, car.model_year)
            fields_to_update.append('ficha_tecnica')
        except Exception as e:
            print(f"[AI] Erro ao obter ficha técnica para carro {car_id}: {e}", flush=True)

    if fields_to_update:
        # update_fields evita disparar o pre_save novamente (sem loop)
        car.save(update_fields=fields_to_update)
        print(f"[AI] Campos {fields_to_update} atualizados para carro {car_id}", flush=True)


def send_price_drop_alerts(car_id, old_price, new_price):
    from cars.models import Car, PriceAlert
    from django.core.mail import send_mail
    from django.conf import settings
    try:
        car = Car.objects.select_related('brand').get(pk=car_id)
        alerts = PriceAlert.objects.filter(car=car)
        if not alerts.exists():
            return
            
        subject = f"Alerta de Preço: O {car.brand.name} {car.model} baixou de preço!"
        for alert in alerts:
            message = (
                f"Olá!\n\n"
                f"Temos boas notícias para você. O veículo {car.brand.name} {car.model} que você favoritou no AutoDrive teve uma redução de preço!\n\n"
                f"De: {car.currency} {old_price} para {car.currency} {new_price}!\n\n"
                f"Aproveite e confira os detalhes no site: http://localhost:5173/car_detail/?id={car.id}\n\n"
                f"Atenciosamente,\nEquipe AutoDrive"
            )
            try:
                send_mail(
                    subject,
                    message,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@autodrive.com'),
                    [alert.email],
                    fail_silently=True
                )
                print(f"[Alert] E-mail de redução de preço enviado para {alert.email} ({car.brand.name} {car.model})", flush=True)
            except Exception as email_err:
                print(f"[Alert] Erro ao enviar e-mail para {alert.email}: {email_err}", flush=True)
    except Exception as e:
        print(f"[Alert] Erro na rotina de alertas de redução de preço: {e}", flush=True)


# pre_save detecta redução de preço e alterações de modelo/marca
@receiver(pre_save, sender=Car)
def car_pre_save(sender, instance, **kwargs):
    if instance.id:
        try:
            old_car = Car.objects.get(pk=instance.id)
            if old_car.value and instance.value and instance.value < old_car.value:
                thread = threading.Thread(target=send_price_drop_alerts, args=(instance.id, old_car.value, instance.value))
                thread.daemon = True
                thread.start()
            
            # Se o modelo ou marca mudar, e anteriormente não havia foto encontrada,
            # resetamos o campo photo_url para re-disparar a busca com os novos dados
            if (old_car.model != instance.model or old_car.brand_id != instance.brand_id) and old_car.photo_url == 'no_photo':
                instance.photo_url = ''
        except Car.DoesNotExist:
            pass


@receiver(post_save, sender=Car)
def car_post_save(sender, instance, created, **kwargs):
    if getattr(instance, 'skip_signal', False):
        return
    car_invetory_update()

    # Só dispara IA e foto quando houver campos faltando (evita re-trigger de update_fields)
    needs_ai = not instance.bio or not instance.categoria or not instance.ficha_tecnica
    needs_photo = not instance.photo and not instance.photo_url

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
