import os
import sys
import csv
import json
import re
import urllib.parse
import requests
import time
from dotenv import load_dotenv
from groq import Groq
from django.core.files.base import ContentFile

# 1. Carregar variáveis de ambiente do diretório pai (.env) ANTES do django setup
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(backend_path, '.env')
load_dotenv(dotenv_path)

# 2. Configurar o ambiente Django para o script rodar de forma independente
if backend_path not in sys.path:
    sys.path.append(backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

# Agora podemos importar os modelos do Django com segurança
from cars.models import Brand, Car

# 3. Validar chaves de API e inicializar cliente
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    raise ValueError("A variável de ambiente GROQ_API_KEY não foi encontrada no arquivo .env.")

client = Groq(api_key=GROQ_API_KEY)

import hashlib
from cars.utils import get_existing_photo_hashes

def get_car_image_data(make, model, year, existing_hashes):
    """
    Busca uma imagem do carro diretamente no Wikimedia Commons e retorna (url, content) da primeira imagem única.
    """
    headers = {"User-Agent": "CarrosBot/1.0 (cmsampaio71@gmail.com)"}
    search_url = "https://commons.wikimedia.org/w/api.php"
    
    # Adicionando o ano na busca para maior precisão
    search_params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{make} {model} {year} car filetype:bitmap",
        "gsrlimit": 5,
        "prop": "imageinfo",
        "iiprop": "url",
        "iiurlwidth": 1000,
        "format": "json"
    }
    
    try:
        res = requests.get(search_url, params=search_params, headers=headers, timeout=10).json()
        pages = res.get("query", {}).get("pages", {})
        
        pages_list = list(pages.values())
        pages_list.sort(key=lambda x: x.get("index", 999))
        
        for page_data in pages_list:
            title = page_data.get("title", "").lower()
            if "imageinfo" in page_data:
                image_info = page_data["imageinfo"][0]
                url = image_info.get("thumburl") or image_info.get("url")
                
                # Ignorar imagens que parecem ser logos ou emblemas
                if "logo" not in url.lower() and "emblem" not in url.lower() and "logo" not in title and "emblem" not in title and "badge" not in title:
                    try:
                        img_res = requests.get(url, headers=headers, timeout=15)
                        if img_res.status_code == 200:
                            content = img_res.content
                            img_hash = hashlib.md5(content).hexdigest()
                            if img_hash not in existing_hashes:
                                return url, content
                            else:
                                print(f"   [Duplicada Ignorada] Hash {img_hash} já existente para outro carro. Skipping: {url}", flush=True)
                    except Exception:
                        pass
    except Exception as e:
        print(f"   [Erro API Commons] {e}", flush=True)
        
    return None, None

def download_and_save_image(car_obj, url_and_content):
    """
    Salva a imagem baixada no campo photo do modelo Car.
    O Django Cloudinary Storage cuidará do upload para o Cloudinary automaticamente.
    """
    if not url_and_content or not url_and_content[1]:
        return False
        
    image_url, content = url_and_content
    try:
        print(f"   [Imagem] Salvando de: {image_url}", flush=True)
        file_name = f"{car_obj.brand.name}_{car_obj.model}_{car_obj.model_year or 'unknown'}.jpg".replace(" ", "_").lower()
        car_obj.photo.save(file_name, ContentFile(content), save=True)
        print(f"   [Sucesso] Imagem salva para {car_obj.model}", flush=True)
        return True
    except Exception as e:
        print(f"   [Erro] Exceção ao salvar imagem: {e}", flush=True)
    return False

def get_car_models_from_ai(brand_name, num_cars=5):
    """
    Usa a IA da Groq para gerar modelos populares de uma marca
    retornando os dados estruturados em JSON.
    """
    prompt = f"""
    Você é um especialista em automóveis. Forneça uma lista com {num_cars} modelos de carros populares ou conhecidos da marca '{brand_name}' no Brasil.
    Para cada carro, você deve fornecer as seguintes informações exatas em formato JSON:
    - "model": Nome do modelo (ex: "Civic", "Corolla", "M3")
    - "value": Valor de mercado real ou Tabela FIPE aproximado em Reais no Brasil (Float, ex: 150000.0). NÃO subestime preços de veículos de luxo ou importados (ex: Porsche, Ferrari, BMW, Mercedes-Benz, Land Rover devem refletir os valores reais de mercado, como 400000.0, 600000.0, ou mais).
    - "factory_year": Ano de fabricação aproximado (Integer, ex: 2022)
    - "model_year": Ano do modelo aproximado (Integer, ex: 2023)

    Retorne APENAS um array JSON válido contendo os objetos de carros, sem nenhuma outra explicação ou formatação Markdown fora do bloco JSON.
    Exemplo de formato esperado:
    [
      {{"model": "Exemplo", "value": 120000.0, "factory_year": 2022, "model_year": 2023}}
    ]
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        # Se for um dicionário e contiver a lista dentro de alguma chave, extraímos
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    data = val
                    break
            if isinstance(data, dict) and "model" in data:
                data = [data]

        clean_cars = []
        # Garante o nivelamento e achatamento (flattening) de listas aninhadas
        if isinstance(data, list):
            for item in data:
                if isinstance(item, list):
                    for sub_item in item:
                        if isinstance(sub_item, dict):
                            clean_cars.append(sub_item)
                elif isinstance(item, dict):
                    clean_cars.append(item)
        return clean_cars
    except Exception as e:
        print(f"Erro ao consultar IA para a marca {brand_name}: {e}", flush=True)
        return []

def main():
    csv_file_path = os.path.join(backend_path, 'brands.csv')
    if not os.path.exists(csv_file_path):
        print(f"Erro: O arquivo brands.csv não foi encontrado em {csv_file_path}", flush=True)
        return

    print("Iniciando importação de carros com IA...", flush=True)
    
    existing_hashes = get_existing_photo_hashes()
    processed_count = 0
    with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        
        for row in reader:
            if not row:
                continue
            
            brand_name = row[0].strip()
            if not brand_name:
                continue


            processed_count += 1
            print(f"\n[{processed_count}] Processando marca: {brand_name}...", flush=True)
            
            brand_obj, created = Brand.objects.get_or_create(name=brand_name)
            if created:
                print(f"-> Marca '{brand_name}' criada no banco de dados.", flush=True)
            
            # Busca 5 modelos sugeridos pela IA
            car_list = get_car_models_from_ai(brand_name, num_cars=5)
            
            for car_data in car_list:
                if not isinstance(car_data, dict):
                    continue
                model_name = car_data.get("model")
                if not model_name:
                    continue
                
                # Evita duplicar o mesmo modelo para a mesma marca
                car_obj, car_created = Car.objects.get_or_create(
                    model=model_name,
                    brand=brand_obj,
                    defaults={
                        'value': car_data.get("value"),
                        'factory_year': car_data.get("factory_year"),
                        'model_year': car_data.get("model_year"),
                    }
                )
                
                if car_created:
                    print(f"   [Adicionado] {brand_name} {model_name} - R$ {car_obj.value} ({car_obj.model_year})", flush=True)
                    # Busca e salva a imagem do carro
                    url_and_content = get_car_image_data(brand_name, model_name, car_obj.model_year or 2023, existing_hashes)
                    if url_and_content[1]:
                        download_and_save_image(car_obj, url_and_content)
                        existing_hashes.add(hashlib.md5(url_and_content[1]).hexdigest())
                else:
                    # Se o carro já existe mas não tem foto, tenta baixar uma
                    if not car_obj.photo:
                        print(f"   [Atualizando] {brand_name} {model_name} (Sem foto)", flush=True)
                        url_and_content = get_car_image_data(brand_name, model_name, car_obj.model_year or 2023, existing_hashes)
                        if url_and_content[1]:
                            download_and_save_image(car_obj, url_and_content)
                            existing_hashes.add(hashlib.md5(url_and_content[1]).hexdigest())
                    else:
                        print(f"   [Ignorado] {brand_name} {model_name} (Já existente com foto)", flush=True)

if __name__ == '__main__':
    main()
