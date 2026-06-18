import os
import sys
import json
import re
import asyncio
import httpx
from dotenv import load_dotenv
from groq import AsyncGroq
from asgiref.sync import sync_to_async

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
from cars.models import Car

# 3. Validar chaves de API e inicializar cliente Groq assíncrono
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

if not GROQ_API_KEY:
    print("[Erro] A variável de ambiente GROQ_API_KEY não foi encontrada no arquivo .env.")
    sys.exit(1)

client = AsyncGroq(api_key=GROQ_API_KEY)
# Semáforo para controlar concorrência (mantido baixo para evitar sobrecarga local)
SEMAPHORE = asyncio.Semaphore(2)
# Bloqueio assíncrono para garantir que apenas um request de preço rode por vez no intervalo de tempo
GROQ_LOCK = asyncio.Lock()

def clean_string(s):
    """
    Remove caracteres invisíveis e de marcação de ordem de byte (BOM - \ufeff)
    que causam duplicidade e quebra nas buscas de APIs.
    """
    if not s:
        return ""
    s = s.replace('\ufeff', '').replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')
    return s.strip()

def get_full_car_name(brand, model):
    """
    Retorna o nome completo do carro sem duplicar a marca caso o modelo já comece com ela.
    """
    b = clean_string(brand)
    m = clean_string(model)
    if m.lower().startswith(b.lower()):
        return m
    return f"{b} {m}"

def parse_price_string(price_str):
    """
    Trata qualquer formato de preço (brasileiro ou internacional, com pontos e vírgulas)
    e converte de forma segura para float.
    """
    price_str = re.sub(r'[^\d.,]', '', price_str)
    if not price_str:
        return None
        
    if ',' in price_str and '.' in price_str:
        if price_str.rfind(',') > price_str.rfind('.'):
            price_str = price_str.replace('.', '').replace(',', '.')
        else:
            price_str = price_str.replace(',', '')
    elif ',' in price_str:
        parts = price_str.split(',')
        if len(parts[-1]) in [1, 2]:
            price_str = "".join(parts[:-1]) + "." + parts[-1]
        else:
            price_str = "".join(parts)
    elif '.' in price_str:
        parts = price_str.split('.')
        if len(parts[-1]) in [1, 2]:
            price_str = "".join(parts[:-1]) + "." + parts[-1]
        else:
            price_str = "".join(parts)
            
    try:
        return float(price_str)
    except ValueError:
        return None

async def is_car_photo_broken(http_client, car):
    """
    Verifica se a foto atual do carro é válida checando se o arquivo existe
    fisicamente na pasta backend/images/.
    """
    if not car.photo:
        return True
    
    photo_path_str = str(car.photo)
    if not photo_path_str:
        return True

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    local_file_path = os.path.join(backend_dir, photo_path_str.replace('/', os.sep))
    return not os.path.exists(local_file_path)

async def get_real_car_price_from_ai(brand, model, year):
    """
    Usa o modelo da Groq de forma assíncrona para obter o preço real (Tabela FIPE) no Brasil.
    Garante um espaçamento de no mínimo 2.2 segundos entre chamadas para respeitar o limite de 30 RPM.
    """
    full_name = get_full_car_name(brand, model)
    
    prompt = f"""
    Você é um especialista em preços de automóveis no Brasil.
    Qual é o valor médio real de mercado ou Tabela FIPE no Brasil (em Reais) para o carro: {full_name} ano {year or 'recente'}?
    Retorne a resposta estritamente no formato JSON abaixo:
    {{
      "preco": 150000.00
    }}
    NÃO adicione nenhuma outra explicação, texto ou formatação Markdown fora do bloco JSON.
    """
    
    async with GROQ_LOCK:
        for attempt in range(5):
            try:
                response = await client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=80,
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                # Espaçamento estrito para evitar bater 30 RPM
                await asyncio.sleep(2.2)
                
                content = response.choices[0].message.content.strip()
                data = json.loads(content)
                raw_preco = data.get("preco", 0)
                
                if isinstance(raw_preco, str):
                    return parse_price_string(raw_preco)
                return float(raw_preco)
            except Exception as e:
                err_str = str(e)
                if "rate_limit" in err_str.lower() or "429" in err_str:
                    wait_time = 4 + attempt * 4
                    print(f"   [Rate Limit] Limite atingido para {full_name}. Aguardando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"   [Erro AI Preço] Falha ao obter preço para {full_name}: {e}")
                    await asyncio.sleep(2.2)
                    break
    return None

import hashlib
from cars.utils import get_existing_photo_hashes, PHOTO_BLACKLIST, _is_valid_car_image

async def get_car_image_url(http_client, make, model, year, existing_hashes):
    """
    Busca uma imagem do carro no Wikimedia Commons de forma assíncrona.
    Utiliza gsrnamespace: 6 para garantir que apenas arquivos de mídia (File) sejam pesquisados.
    Retorna uma tupla (url, content) da primeira imagem única.
    """
    make_clean = clean_string(make)
    model_clean = clean_string(model)
    full_name = get_full_car_name(make, model)
    
    queries_to_try = [
        f"{make_clean} {model_clean} {year or ''} car",
        full_name,
        f"{make_clean} {model_clean.split()[0]}",
        model_clean
    ]
    
    headers = {"User-Agent": "CarrosBot/1.0 (cmsampaio71@gmail.com)"}
    search_url = "https://commons.wikimedia.org/w/api.php"
    
    for query in queries_to_try:
        query = query.strip()
        if not query:
            continue
            
        search_params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 5,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1000,
            "format": "json"
        }
        
        try:
            await asyncio.sleep(0.2)
            res = await http_client.get(search_url, params=search_params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
                if pages:
                    pages_list = list(pages.values())
                    pages_list.sort(key=lambda x: x.get("index", 999))
                    
                    for page_data in pages_list:
                        title = page_data.get("title", "")
                        if "imageinfo" not in page_data:
                            continue
                        image_info = page_data["imageinfo"][0]
                        url = image_info.get("thumburl") or image_info.get("url", "")
                        url_lower = url.lower()

                        if not any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            continue

                        # Aplica blacklist centralizada (documentos, logos, mapas, etc.)
                        if any(term in url_lower or term in title.lower() for term in PHOTO_BLACKLIST):
                            continue

                        # Baixa a imagem para checar hash MD5 e aspect ratio
                        try:
                            img_res = await http_client.get(url, headers=headers, timeout=15, follow_redirects=True)
                            if img_res.status_code == 200:
                                img_content = img_res.content

                                # Rejeita imagens com aspecto de documento/portrait
                                if not _is_valid_car_image(img_content):
                                    print(f"   [Aspecto Inválido] Rejeitado: {url}")
                                    continue

                                img_hash = hashlib.md5(img_content).hexdigest()
                                if img_hash not in existing_hashes:
                                    return url, img_content
                                else:
                                    print(f"   [Duplicada Ignorada] Hash {img_hash} já existente para outro carro. Skipping: {url}")
                        except Exception:
                            pass
        except Exception:
            pass
            
    return None, None

async def download_and_save_image(car_obj, url_and_content):
    """
    Salva a imagem baixada localmente na pasta backend/images e salva o caminho relativo no Supabase.
    """
    if not url_and_content or not url_and_content[1]:
        return False
        
    image_url, content = url_and_content
    try:
        brand_clean = clean_string(car_obj.brand.name)
        model_clean = clean_string(car_obj.model)
        file_name = f"{brand_clean}_{model_clean}_{car_obj.model_year or 'unknown'}.jpg".replace(" ", "_").lower()
        
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        images_dir = os.path.join(backend_dir, 'images')
        os.makedirs(images_dir, exist_ok=True)
        
        local_path = os.path.join(images_dir, file_name)
        
        # Salva localmente
        with open(local_path, 'wb') as f:
            f.write(content)
        
        # Salva o caminho relativo no banco de dados (Supabase)
        def save_to_db():
            car_obj.photo = f"images/{file_name}"
            car_obj.save()
        
        await sync_to_async(save_to_db)()
        return True
    except Exception as e:
        print(f"   [Erro Mídia] Exceção ao salvar imagem de {car_obj.model}: {e}")
    return False

async def process_single_car(http_client, car, existing_hashes):
    """
    Processa um único carro respeitando o semáforo.
    """
    brand_clean = clean_string(car.brand.name)
    model_clean = clean_string(car.model)
    full_name = get_full_car_name(car.brand.name, car.model)
    
    async with SEMAPHORE:
        print(f"[Iniciando] {full_name} ({car.model_year})")
        
        # 1. Obter e atualizar o preço médio real
        real_value = await get_real_car_price_from_ai(car.brand.name, car.model, car.model_year)
        if real_value:
            def update_value():
                car.value = real_value
                car.save()
            await sync_to_async(update_value)()
            print(f"   [Preço Atualizado] {full_name}: R$ {real_value:,.2f}")
        else:
            print(f"   [Preço Ignorado] {full_name} não atualizado.")
        
        # 2. Obter e atualizar a imagem se a foto atual estiver quebrada (ou se não houver foto)
        photo_broken = await is_car_photo_broken(http_client, car)
        if photo_broken:
            print(f"   [Verificação] Imagem ausente ou quebrada. Buscando nova foto...")
            url_and_content = await get_car_image_url(http_client, car.brand.name, car.model, car.model_year, existing_hashes)
            if url_and_content[1]:
                success = await download_and_save_image(car, url_and_content)
                if success:
                    print(f"   [Imagem Atualizada] {full_name} com nova foto.")
                    existing_hashes.add(hashlib.md5(url_and_content[1]).hexdigest())
                else:
                    print(f"   [Imagem Falhou] Não foi possível salvar a imagem.")
            else:
                print(f"   [Imagem Não Encontrada] Nenhuma foto única encontrada para {full_name}.")
        else:
            print(f"   [Imagem Preservada] {full_name} já possui uma foto válida.")
            
        print(f"[Concluído] {full_name}")
        print("-" * 50)

async def main():
    def get_all_cars():
        return list(Car.objects.select_related('brand').all())
    
    cars = await sync_to_async(get_all_cars)()
    total_cars = len(cars)
    print(f"Iniciando processamento assíncrono de {total_cars} carros cadastrados no banco de dados...\n")
    
    existing_hashes = await sync_to_async(get_existing_photo_hashes)()
    
    async with httpx.AsyncClient() as http_client:
        tasks = [process_single_car(http_client, car, existing_hashes) for car in cars]
        await asyncio.gather(*tasks)

    print("\nProcessamento assíncrono concluído com sucesso!")

if __name__ == '__main__':
    asyncio.run(main())

