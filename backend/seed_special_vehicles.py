import os
import sys
import json
import time
from dotenv import load_dotenv
from groq import Groq
import hashlib

backend_path = os.path.dirname(os.path.abspath(__file__))
dotenv_path = os.path.join(backend_path, '.env')
load_dotenv(dotenv_path)

if backend_path not in sys.path:
    sys.path.append(backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

from cars.models import Brand, Car
from cars.utils import get_existing_photo_hashes

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
client = Groq(api_key=GROQ_API_KEY)

def get_special_vehicles_from_ai(category, description, num_vehicles=10):
    prompt = f"""
    Você é um especialista em veículos do Brasil. Forneça uma lista com {num_vehicles} {description}.
    Para cada veículo, você deve fornecer as seguintes informações exatas em formato JSON:
    - "brand": Nome da marca (ex: "Chevrolet", "Scania", "Honda")
    - "model": Nome do modelo (ex: "Opala Diplomata 4.1", "FH 540", "CG 160 Titan")
    - "value": Valor de mercado real ou Tabela FIPE aproximado em Reais no Brasil (Float, ex: 150000.0)
    - "factory_year": Ano de fabricação aproximado (Integer, ex: 1990)
    - "model_year": Ano do modelo aproximado (Integer, ex: 1991)

    Retorne APENAS um array JSON válido contendo os objetos, sem nenhuma outra explicação.
    Exemplo:
    [
      {{"brand": "Chevrolet", "model": "Opala Diplomata 4.1", "value": 80000.0, "factory_year": 1990, "model_year": 1991}}
    ]
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"): content = content[7:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    data = val
                    break
            if isinstance(data, dict) and "model" in data:
                data = [data]

        clean_vehicles = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list):
                    for sub_item in item:
                        if isinstance(sub_item, dict): clean_vehicles.append(sub_item)
                elif isinstance(item, dict):
                    clean_vehicles.append(item)
        return clean_vehicles
    except Exception as e:
        print(f"Erro ao consultar IA para {category}: {e}", flush=True)
        return []

def main():
    categories = [
        ("Carros Clássicos Brasileiros", "carros clássicos brasileiros muito desejados (ex: Opala, Maverick V8, Dodge Dart, Gol GTI, Fusca, Omega)"),
        ("Caminhões Populares", "caminhões muito famosos e usados nas estradas do Brasil (ex: Scania 113, Volvo FH, Mercedes-Benz Actros, VW Constellation)"),
        ("Motos Famosas", "motocicletas icônicas e muito populares no Brasil, de baixa a alta cilindrada (ex: Honda CG 160, Yamaha XJ6, Suzuki Hayabusa, BMW R1250 GS, Harley-Davidson)")
    ]

    print("Iniciando importação de veículos especiais...")
    existing_hashes = get_existing_photo_hashes()

    for cat_name, desc in categories:
        print(f"\n--- Buscando {cat_name} ---")
        vehicles = get_special_vehicles_from_ai(cat_name, desc, num_vehicles=10)
        
        for v in vehicles:
            brand_name = v.get("brand")
            model_name = v.get("model")
            if not brand_name or not model_name: continue

            brand_obj, _ = Brand.objects.get_or_create(name=brand_name)
            
            car_obj, created = Car.objects.get_or_create(
                model=model_name,
                brand=brand_obj,
                defaults={
                    'value': v.get("value"),
                    'factory_year': v.get("factory_year"),
                    'model_year': v.get("model_year"),
                }
            )
            
            if created:
                print(f"   [Adicionado] {brand_name} {model_name} - R$ {car_obj.value}")
            else:
                print(f"   [Ignorado] {brand_name} {model_name} (Já existente)")
            
            time.sleep(1)

if __name__ == '__main__':
    main()
