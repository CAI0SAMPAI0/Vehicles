import os
import sys
import csv
import json
import re
import urllib.parse
import requests
from dotenv import load_dotenv
from groq import Groq
from django.core.files.base import ContentFile

# 1. Configurar o ambiente Django para o script rodar de forma independente
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_path not in sys.path:
    sys.path.append(backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

# Agora podemos importar os modelos do Django com segurança
from cars.models import Brand, Car

# 2. Carregar variáveis de ambiente
load_dotenv()
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

if not GROQ_API_KEY:
    raise ValueError("A variável de ambiente GROQ_API_KEY não foi encontrada no arquivo .env.")

client = Groq(api_key=GROQ_API_KEY)

def get_car_image_url(brand_name, model_name, year):
    """
    Busca na internet (Bing Images) uma imagem correspondente ao carro e retorna a URL direta.
    """
    query = f"{brand_name} {model_name} {year} carro"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    url = f"https://www.bing.com/images/search?q={urllib.parse.quote(query)}&__noscript=1"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Captura a URL direta da imagem contida na tag "murl" do HTML do Bing
            urls = re.findall(r'"murl":"(http[^"]+)"', response.text)
            if urls:
                return urls[0]
    except Exception as e:
        print(f"   [Erro Busca Imagem] Não foi possível buscar imagem para '{query}': {e}")
    return None

def download_and_save_car_image(car_obj, image_url):
    """
    Faz o download da imagem a partir da URL e a salva no ImageField do modelo Car.
    """
    if not image_url:
        return False
    try:
        response = requests.get(image_url, timeout=10)
        if response.status_code == 200:
            filename = f"{car_obj.brand.name}_{car_obj.model}_{car_obj.model_year}.jpg".replace(" ", "_").lower()
            # Salva o conteúdo no ImageField do Django (faz upload automático para Cloudinary / Mídia local)
            car_obj.photo.save(filename, ContentFile(response.content), save=True)
            return True
    except Exception as e:
        print(f"   [Erro Download Imagem] Falha ao baixar/salvar imagem de {image_url}: {e}")
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

    print("Iniciando importação de carros com IA e imagens...", flush=True)
    
    processed_count = 0
    with open(csv_file_path, mode='r', encoding='utf-8') as f:
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
                
                # Se o carro acabou de ser criado, ou se já existe mas não possui imagem
                if car_created or not car_obj.photo:
                    if not car_created:
                        print(f"   [Sem Imagem] {brand_name} {model_name} (Existente) - Buscando imagem...", flush=True)
                    else:
                        print(f"   [Adicionado] {brand_name} {model_name} - R$ {car_obj.value} ({car_obj.model_year})", flush=True)
                    
                    # Busca imagem e faz download
                    img_url = get_car_image_url(brand_name, model_name, car_obj.model_year)
                    if img_url:
                        success = download_and_save_car_image(car_obj, img_url)
                        if success:
                            print(f"      -> Imagem baixada e salva com sucesso!", flush=True)
                        else:
                            print(f"      -> Falha ao salvar a imagem.", flush=True)
                    else:
                        print(f"      -> Nenhuma imagem encontrada na busca.", flush=True)
                else:
                    print(f"   [Ignorado] {brand_name} {model_name} (Já existe com imagem)", flush=True)

if __name__ == '__main__':
    main()
