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

def get_car_image_url(make, model, year):
    """
    Busca a imagem principal de um artigo da Wikipedia para o carro.
    """
    query = f"{make} {model}"
    headers = {"User-Agent": "CarrosBot/1.0 (seu-email@exemplo.com)"}
    
    # Tenta em português e depois em inglês
    for lang in ["pt", "en"]:
        search_url = f"https://{lang}.wikipedia.org/w/api.php"
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "srlimit": 1
        }
        
        try:
            res = requests.get(search_url, params=search_params, headers=headers, timeout=10).json()
            search_results = res.get("query", {}).get("search", [])
            if search_results:
                title = search_results[0]["title"]
                
                img_params = {
                    "action": "query",
                    "titles": title,
                    "prop": "pageimages",
                    "format": "json",
                    "pithumbsize": 1000
                }
                img_res = requests.get(search_url, params=img_params, headers=headers, timeout=10).json()
                pages = img_res.get("query", {}).get("pages", {})
                for page_id in pages:
                    if "thumbnail" in pages[page_id]:
                        return pages[page_id]["thumbnail"]["source"]
        except Exception:
            continue
    return None

def download_and_save_image(car_obj, image_url):
    """
    Baixa a imagem da URL e salva no campo photo do modelo Car.
    O Django Cloudinary Storage cuidará do upload para o Cloudinary automaticamente.
    """
    if not image_url:
        return False
        
    try:
        print(f"   [Imagem] Baixando: {image_url}", flush=True)
        response = requests.get(image_url, timeout=15)
        if response.status_code == 200:
            file_name = f"{car_obj.brand.name}_{car_obj.model}_{car_obj.model_year or 'unknown'}.jpg".replace(" ", "_").lower()
            car_obj.photo.save(file_name, ContentFile(response.content), save=True)
            print(f"   [Sucesso] Imagem salva para {car_obj.model}", flush=True)
            return True
        else:
            print(f"   [Erro] Falha ao baixar imagem (Status: {response.status_code})", flush=True)
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
    - "value": Valor aproximado em Reais (Float, ex: 150000.0)
    - "factory_year": Ano de fabricação aproximado (Integer, ex: 2022)
    - "model_year": Ano do modelo aproximado (Integer, ex: 2023)
    - "bio": Uma breve descrição de venda do carro em no máximo 200 caracteres, destacando seus principais atrativos.

    Retorne APENAS um array JSON válido contendo os objetos de carros, sem nenhuma outra explicação ou formatação Markdown fora do bloco JSON.
    Exemplo de formato esperado:
    [
      {{"model": "Exemplo", "value": 120000.0, "factory_year": 2022, "model_year": 2023, "bio": "Excelente carro."}}
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
    
    processed_count = 0
    with open(csv_file_path, mode='r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        
        for row in reader:
            if not row:
                continue
            
            brand_name = row[0].strip()
            if not brand_name:
                continue

            # Pergunta se deseja continuar a cada 15 marcas processadas
            if processed_count > 0 and processed_count % 15 == 0:
                print(f"\n--- Lote de 15 marcas finalizado! ({processed_count} marcas processadas até agora) ---", flush=True)
                choice = input("Deseja continuar com as próximas 15 marcas? (S/n): ").strip().lower()
                if choice == 'n':
                    print("Processamento pausado pelo usuário. Finalizando script.", flush=True)
                    break

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
                        'bio': car_data.get("bio", "")
                    }
                )
                
                if car_created:
                    print(f"   [Adicionado] {brand_name} {model_name} - R$ {car_obj.value} ({car_obj.model_year})", flush=True)
                    # Busca e salva a imagem do carro
                    image_url = get_car_image_url(brand_name, model_name, car_obj.model_year or 2023)
                    download_and_save_image(car_obj, image_url)
                else:
                    # Se o carro já existe mas não tem foto, tenta baixar uma
                    if not car_obj.photo:
                        print(f"   [Atualizando] {brand_name} {model_name} (Sem foto)", flush=True)
                        image_url = get_car_image_url(brand_name, model_name, car_obj.model_year or 2023)
                        download_and_save_image(car_obj, image_url)
                    else:
                        print(f"   [Ignorado] {brand_name} {model_name} (Já existente com foto)", flush=True)

if __name__ == '__main__':
    main()
