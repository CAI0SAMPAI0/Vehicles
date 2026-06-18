"""
Script para popular o banco de dados com carros clássicos e vintage brasileiros.
Execute manualmente com: python backend/openai_api/add_vintage_cars.py

Os carros são adicionados com categoria = 'CLASSICO' automaticamente.
"""
import os
import sys
import hashlib
import requests
from dotenv import load_dotenv

# Configurar ambiente Django
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(backend_path, '.env')
load_dotenv(dotenv_path)

if backend_path not in sys.path:
    sys.path.append(backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

from django.core.files.base import ContentFile
from cars.models import Brand, Car
from cars.utils import PHOTO_BLACKLIST, _is_valid_car_image, get_existing_photo_hashes
from openai_api.client import get_car_ai_bio

# ─────────────────────────────────────────────
# Lista de carros clássicos a serem adicionados
# ─────────────────────────────────────────────
CARROS_CLASSICOS = [
    # Volkswagen
    {"brand": "Volkswagen", "model": "Fusca",       "factory_year": 1970, "model_year": 1970, "value": 35000.0},
    {"brand": "Volkswagen", "model": "Fusca",       "factory_year": 1980, "model_year": 1980, "value": 42000.0},
    {"brand": "Volkswagen", "model": "Kombi",       "factory_year": 1975, "model_year": 1975, "value": 55000.0},
    {"brand": "Volkswagen", "model": "Brasília",    "factory_year": 1978, "model_year": 1978, "value": 28000.0},
    {"brand": "Volkswagen", "model": "Gol GL",      "factory_year": 1983, "model_year": 1984, "value": 22000.0},
    {"brand": "Volkswagen", "model": "SP2",         "factory_year": 1976, "model_year": 1976, "value": 95000.0},
    # Chevrolet / GM
    {"brand": "Chevrolet",  "model": "Opala",       "factory_year": 1975, "model_year": 1975, "value": 65000.0},
    {"brand": "Chevrolet",  "model": "Opala Coupe", "factory_year": 1980, "model_year": 1980, "value": 85000.0},
    {"brand": "Chevrolet",  "model": "Chevette",    "factory_year": 1982, "model_year": 1982, "value": 30000.0},
    {"brand": "Chevrolet",  "model": "Veraneio",    "factory_year": 1985, "model_year": 1985, "value": 70000.0},
    {"brand": "Chevrolet",  "model": "Camaro",      "factory_year": 1979, "model_year": 1979, "value": 180000.0},
    # Ford
    {"brand": "Ford",       "model": "Maverick",    "factory_year": 1977, "model_year": 1977, "value": 75000.0},
    {"brand": "Ford",       "model": "Corcel",      "factory_year": 1973, "model_year": 1973, "value": 35000.0},
    {"brand": "Ford",       "model": "Belina",      "factory_year": 1982, "model_year": 1982, "value": 28000.0},
    {"brand": "Ford",       "model": "Del Rey",     "factory_year": 1985, "model_year": 1985, "value": 32000.0},
    {"brand": "Ford",       "model": "Galaxie",     "factory_year": 1972, "model_year": 1972, "value": 120000.0},
    # Fiat
    {"brand": "Fiat",       "model": "147",         "factory_year": 1980, "model_year": 1980, "value": 25000.0},
    {"brand": "Fiat",       "model": "Uno Mille",   "factory_year": 1989, "model_year": 1989, "value": 18000.0},
    # Dodge
    {"brand": "Dodge",      "model": "Charger RT",  "factory_year": 1977, "model_year": 1977, "value": 150000.0},
    # Puma
    {"brand": "Puma",       "model": "GTE",         "factory_year": 1975, "model_year": 1975, "value": 130000.0},
]

HEADERS = {"User-Agent": "CarrosBot/1.0 (cmsampaio71@gmail.com)"}
WIKIMEDIA_URL = "https://commons.wikimedia.org/w/api.php"


def buscar_foto_classico(brand, model, year, existing_hashes):
    """
    Busca foto específica para carros clássicos no Wikimedia Commons.
    Usa queries otimizadas para veículos históricos brasileiros.
    """
    queries = [
        f"{brand} {model} {year}",
        f"{brand} {model} Brasil",
        f"{brand} {model} vintage",
        f"{brand} {model}",
    ]

    for query in queries:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.strip(),
            "gsrnamespace": 6,
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1000,
            "format": "json",
        }

        try:
            res = requests.get(WIKIMEDIA_URL, params=params, headers=HEADERS, timeout=10)
            if res.status_code != 200:
                continue

            pages = res.json().get("query", {}).get("pages", {})
            if not pages:
                continue

            pages_list = sorted(pages.values(), key=lambda x: x.get("index", 999))

            for page_data in pages_list:
                title = page_data.get("title", "")
                if "imageinfo" not in page_data:
                    continue

                image_info = page_data["imageinfo"][0]
                url = image_info.get("thumburl") or image_info.get("url", "")
                url_lower = url.lower()

                if not any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                    continue

                # Aplica blacklist
                if any(term in url_lower or term in title.lower() for term in PHOTO_BLACKLIST):
                    continue

                try:
                    img_res = requests.get(url, headers=HEADERS, timeout=15)
                    if img_res.status_code != 200:
                        continue

                    img_content = img_res.content

                    if not _is_valid_car_image(img_content):
                        print(f"   [Aspecto Inválido] Rejeitado: {url}")
                        continue

                    img_hash = hashlib.md5(img_content).hexdigest()
                    if img_hash in existing_hashes:
                        print(f"   [Duplicada] Pulando: {url}")
                        continue

                    return url, img_content, img_hash

                except Exception as e:
                    print(f"   [Erro Download] {url}: {e}")

        except Exception as e:
            print(f"   [Erro Wikimedia] Query '{query}': {e}")

    return None, None, None


def main():
    print("=" * 60)
    print("  ADICIONANDO CARROS CLÁSSICOS / VINTAGE AO BANCO DE DADOS")
    print("=" * 60)

    existing_hashes = get_existing_photo_hashes()
    adicionados = 0
    ignorados = 0

    for dados in CARROS_CLASSICOS:
        brand_name = dados["brand"]
        model_name = dados["model"]
        year = dados["factory_year"]

        brand_obj, _ = Brand.objects.get_or_create(name=brand_name)

        # Evita duplicar o mesmo modelo + ano para a mesma marca
        car_obj, criado = Car.objects.get_or_create(
            model=model_name,
            brand=brand_obj,
            factory_year=year,
            defaults={
                'model_year': dados.get("model_year", year),
                'value': dados.get("value"),
                'categoria': 'CLASSICO',
            }
        )

        if not criado:
            print(f"[Ignorado] {brand_name} {model_name} {year} (já existe)")
            ignorados += 1
            # Atualiza categoria se estiver vazia
            if not car_obj.categoria:
                car_obj.categoria = 'CLASSICO'
                car_obj.save(update_fields=['categoria'])
            continue

        # Gera bio via IA
        if not car_obj.bio:
            try:
                bio = get_car_ai_bio(model_name, brand_name, year)
                car_obj.bio = bio
                car_obj.save(update_fields=['bio'])
            except Exception as e:
                print(f"   [Bio] Erro ao gerar bio: {e}")

        # Busca foto
        print(f"[Adicionando] {brand_name} {model_name} {year}...")
        url, content, img_hash = buscar_foto_classico(brand_name, model_name, year, existing_hashes)

        if content:
            file_name = f"{brand_name}_{model_name}_{year}.jpg".replace(" ", "_").lower()
            car_obj.photo.save(file_name, ContentFile(content), save=True)
            existing_hashes.add(img_hash)
            print(f"   [Foto] Salva de: {url}")
        else:
            print(f"   [Foto] Nenhuma foto única encontrada. Continuando sem foto.")

        adicionados += 1

    print("\n" + "=" * 60)
    print(f"  Concluído! {adicionados} carros adicionados, {ignorados} ignorados.")
    print("=" * 60)


if __name__ == '__main__':
    main()
