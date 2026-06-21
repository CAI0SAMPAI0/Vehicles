import os
import sys
import time
import requests
from datetime import datetime
from django.db.models import Q

def ping_self():
    """
    Realiza uma chamada HTTP GET para a URL pública do Hugging Face Space (ou localhost)
    para registrar tráfego e evitar que o contêiner durma.
    """
    space_host = os.getenv('SPACE_HOST')
    space_id = os.getenv('SPACE_ID')
    
    url = None
    if space_host:
        url = f"https://{space_host}/"
    elif space_id and '/' in space_id:
        user, space = space_id.split('/')
        user_name = user.replace('.', '-').replace('_', '-').lower()
        space_name = space.replace('.', '-').replace('_', '-').lower()
        url = f"https://{user_name}-{space_name}.hf.space/"
        
    if not url:
        url = "http://localhost:7860/"
        
    print(f"[{datetime.now()}] [Keep-Alive] Pinging self at {url}...", flush=True)
    try:
        response = requests.get(url, timeout=15)
        print(f"[{datetime.now()}] [Keep-Alive] Ping response status: {response.status_code}", flush=True)
    except Exception as e:
        print(f"[{datetime.now()}] [Keep-Alive] Failed to ping self: {e}", flush=True)

def auto_update_cars():
    """
    Varre o banco de dados buscando carros com informações incompletas
    (categoria, bio ou foto) e as preenche automaticamente usando a IA e buscas na internet.
    """
    from cars.models import Car
    from cars.signals import car_post_save
    from django.db.models.signals import post_save
    from openai_api.client import get_car_ai_category, get_car_ai_bio
    from cars.utils import fetch_and_save_car_photo_with_hashes, get_existing_photo_hashes
    
    print(f"[{datetime.now()}] [Background Worker] Checking for cars with missing info...", flush=True)
    
    # Busca carros que não possuem categoria, bio ou foto
    cars_to_update = Car.objects.filter(
        Q(photo='') | Q(photo__isnull=True) |
        Q(categoria='') | Q(categoria__isnull=True) | Q(categoria=None) |
        Q(bio='') | Q(bio__isnull=True)
    )
    
    if not cars_to_update.exists():
        print(f"[{datetime.now()}] [Background Worker] All cars are up to date.", flush=True)
        return
        
    print(f"[{datetime.now()}] [Background Worker] Found {cars_to_update.count()} cars needing updates.", flush=True)
    
    # Desconecta os sinais do Django para evitar loops de post_save recursivos
    post_save.disconnect(car_post_save, sender=Car)
    
    try:
        # Obtém o conjunto de hashes de fotos existentes para evitar baixar a mesma foto
        existing_hashes = get_existing_photo_hashes()
        
        for car in cars_to_update:
            brand_name = car.brand.name
            model_name = car.model
            full_name = f"{brand_name} {model_name}"
            
            print(f"[{datetime.now()}] [Background Worker] Processing {full_name}...", flush=True)
            
            updated_fields = []
            
            # 1. Atualizar categoria se faltar
            if not car.categoria:
                try:
                    categoria = get_car_ai_category(car.brand, car.model, car.model_year)
                    if categoria:
                        car.categoria = categoria
                        updated_fields.append('categoria')
                        print(f"   [Categoria] Definida como: {categoria}", flush=True)
                except Exception as e:
                    print(f"   [Categoria Erro] Erro ao classificar: {e}", flush=True)
            
            # 2. Atualizar bio se faltar
            if not car.bio:
                try:
                    bio = get_car_ai_bio(car.model, car.brand, car.model_year)
                    if bio:
                        car.bio = bio
                        updated_fields.append('bio')
                        print(f"   [Bio] Bio gerada com sucesso.", flush=True)
                except Exception as e:
                    print(f"   [Bio Erro] Erro ao gerar bio: {e}", flush=True)
            
            # Salva os campos de texto primeiro se mudaram
            if updated_fields:
                car.save(update_fields=updated_fields)
                
            # 3. Atualizar foto se faltar
            if not car.photo:
                try:
                    print(f"   [Foto] Buscando foto na internet...", flush=True)
                    fetch_and_save_car_photo_with_hashes(car.id, existing_hashes)
                except Exception as e:
                    print(f"   [Foto Erro] Erro ao buscar/salvar foto: {e}", flush=True)
                    
            # Pequeno intervalo para respeitar limites de requisição de APIs
            time.sleep(2)
            
    except Exception as e:
        print(f"[{datetime.now()}] [Background Worker Error] Ocorreu uma exceção no processamento: {e}", flush=True)
    finally:
        # Reconecta os sinais ao finalizar
        post_save.connect(car_post_save, sender=Car)

def worker_loop():
    """
    Loop principal do worker em segundo plano.
    Executa a primeira checagem após inicialização e depois roda periodicamente.
    """
    print(f"[{datetime.now()}] [Background Worker] Starting background loop thread...", flush=True)
    
    # Aguarda o servidor estar completamente no ar
    time.sleep(10)
    
    # Executa primeiro ping e processamento imediatamente
    ping_self()
    auto_update_cars()
    
    # Loop contínuo a cada 10 minutos (600 segundos)
    while True:
        try:
            time.sleep(600)
            ping_self()
            auto_update_cars()
        except Exception as e:
            print(f"[{datetime.now()}] [Background Worker Exception] {e}", flush=True)
