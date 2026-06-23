import io
import os
import re
import hashlib
import requests
from django.core.files.base import ContentFile
from django.db.models.signals import post_save
from datetime import datetime


PHOTO_BLACKLIST = [
    "logo", "emblem", "badge", "drawing", "diagram", "interior",
    "document", "mapa", "map", "pdf", "chart", "graph",
    "schematic", "blueprint", "brochure",
    "advertisement", "catalogue", "catalog", "flyer",
    "manual", "aerial", "satellite", "coat_of_arms", "flag",
    "symbol", "stamp", "gun", "weapon", "pistol", "firearm",
    "sig", "sauer", "rifle", "artillery", "municipality",
    "city", "town", "village", "province", "county", "album",
    "band", "song", "movie", "book", "building", "architecture",
]


def _is_valid_car_image(content: bytes) -> bool:
    """
    Verifica se a imagem baixada tem aspecto plausível para um carro.
    Rejeita imagens com proporção de documento (portrait A4 = mais alta que larga).
    Retorna True se a imagem for válida.
    """
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(content))
        w, h = img.size
        if w == 0 or h == 0:
            return False
        ratio = h / w
        # Rejeita se a imagem for mais alta que larga por mais de 20% (documentos, PDFs)
        if ratio > 1.2:
            return False
        # Rejeita imagens minúsculas (logos ou ícones)
        if w < 300 or h < 150:
            return False
        return True
    except Exception:
        # Se não conseguir abrir com PIL, aceita por padrão
        return True


def get_existing_photo_hashes():
    """
    Calcula e retorna um conjunto de hashes MD5 de todas as fotos de carros válidas existentes.
    Ignora silenciosamente arquivos inexistentes (comum após novas implantações na Render).
    """
    hashes = set()
    from cars.models import Car
    for car in Car.objects.exclude(photo='').exclude(photo__isnull=True):
        try:
            if car.photo:
                car.photo.open('rb')
                content = car.photo.read()
                car.photo.close()
                if content:
                    file_hash = hashlib.md5(content).hexdigest()
                    hashes.add(file_hash)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Erro ao calcular hash para o carro {car.id}: {e}")
    return hashes


def _url_is_blacklisted(url: str, title: str) -> bool:
    """Verifica se a URL ou o título da imagem contém termos proibidos.
    Usa word boundaries (\\b) para evitar falsos positivos como 'ad' em 'upload',
    'sign' em 'design', 'plan' em 'explanation', etc.
    """
    combined = (url + " " + title).lower()
    for term in PHOTO_BLACKLIST:
        # \b garante que o termo é uma palavra completa, não substring
        if re.search(r'\b' + re.escape(term) + r'\b', combined):
            return True
    return False


def _try_save_photo_url(car, url, brand_name, model_name):
    """Tenta salvar uma URL de foto no banco. Retorna True se salvou com sucesso."""
    try:
        car.skip_signal = True
        car.photo_url = url
        car.save(update_fields=['photo_url'])
        print(f"   [Sucesso] URL salva para {brand_name} {model_name}: {url}", flush=True)
        from django.core.cache import cache
        try:
            cache.clear()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"   [Erro ao salvar URL] {url}: {e}", flush=True)
        return False


def _fetch_wikipedia_thumbnail(brand_name, model_name, year, headers):
    """
    Tenta buscar a thumbnail do artigo da Wikipedia (en/pt) para o carro.
    Usa a prop=pageimages da API da Mediawiki, que retorna a imagem principal do artigo.
    Retorna a URL da thumbnail se encontrar, ou None.
    """
    # Termos de busca para o título do artigo (do mais específico ao mais genérico)
    search_titles = [
        f"{brand_name} {model_name} ({year})" if year else None,
        f"{brand_name} {model_name}",
        f"{model_name} ({brand_name})",
        model_name,
    ]

    for wiki_lang in ['en', 'pt']:
        api_url = f"https://{wiki_lang}.wikipedia.org/w/api.php"
        for title in search_titles:
            if not title:
                continue
            try:
                # 1. Busca o artigo mais relevante
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": title,
                    "srlimit": 3,
                    "srprop": "snippet",
                    "format": "json",
                }
                res = requests.get(api_url, params=search_params, headers=headers, timeout=8)
                if res.status_code != 200:
                    continue
                results = res.json().get("query", {}).get("search", [])
                if not results:
                    continue

                # Valida se o artigo parece ser sobre um veículo (evitar armas, bandas, lugares)
                valid_article = None
                vehicle_terms = ['car', 'truck', 'bus', 'vehicle', 'auto', 'van', 'suv', 'motorcycle', 'caminhão', 'carro', 'ônibus', 'tractor', 'engine', 'motor', 'pickup', 'picape', 'sedan', 'hatch']
                brand_lower = brand_name.lower()
                
                for r in results:
                    snippet = r.get("snippet", "").lower()
                    r_title = r.get("title", "").lower()
                    has_brand = brand_lower in r_title or brand_lower in snippet
                    has_vehicle = any(term in snippet or term in r_title for term in vehicle_terms)
                    
                    if has_brand or has_vehicle:
                        valid_article = r["title"]
                        break
                        
                if not valid_article:
                    print(f"   [Wikipedia-{wiki_lang}] Artigo rejeitado por falta de contexto automotivo: '{title}'", flush=True)
                    continue

                # Pega o título do artigo mais relevante que passou no filtro
                article_title = valid_article

                # 2. Busca a thumbnail do artigo
                image_params = {
                    "action": "query",
                    "titles": article_title,
                    "prop": "pageimages",
                    "pithumbsize": 1000,
                    "piprop": "thumbnail",
                    "format": "json",
                    "redirects": 1,
                }
                img_res = requests.get(api_url, params=image_params, headers=headers, timeout=8)
                if img_res.status_code != 200:
                    continue

                pages = img_res.json().get("query", {}).get("pages", {})
                for page in pages.values():
                    thumb = page.get("thumbnail", {})
                    thumb_url = thumb.get("source", "")
                    if thumb_url:
                        # Valida que não é logo, bandeira, etc.
                        if _url_is_blacklisted(thumb_url, article_title):
                            print(f"   [Wikipedia-{wiki_lang}] Blacklist rejeitou thumbnail de '{article_title}'", flush=True)
                            continue
                        # Valida aspect ratio com sample
                        try:
                            sample = requests.get(thumb_url, headers=headers, timeout=10, stream=True)
                            if sample.status_code == 200:
                                img_content = b""
                                for chunk in sample.iter_content(chunk_size=8192):
                                    img_content += chunk
                                    if len(img_content) >= 204800:
                                        break
                                sample.close()
                                if _is_valid_car_image(img_content):
                                    print(f"   [Wikipedia-{wiki_lang}] Thumbnail encontrada para '{article_title}': {thumb_url}", flush=True)
                                    return thumb_url
                                else:
                                    print(f"   [Wikipedia-{wiki_lang}] Aspecto inválido rejeitado: {thumb_url}", flush=True)
                        except Exception as e:
                            print(f"   [Wikipedia-{wiki_lang}] Erro ao validar thumbnail: {e}", flush=True)
            except Exception as e:
                print(f"   [Wikipedia-{wiki_lang}] Erro na busca para '{title}': {e}", flush=True)
                continue

    return None


def _fetch_commons_search(brand_name, model_name, year, headers):
    """
    Estratégia de fallback: busca imagens no Wikimedia Commons (namespace 6).
    Retorna a URL da primeira imagem válida encontrada, ou None.
    """
    search_url = "https://commons.wikimedia.org/w/api.php"

    # Gera queries progressivamente mais amplas
    queries_to_try = []
    if year:
        queries_to_try.append(f"{brand_name} {model_name} {year}")
    queries_to_try.append(f"{brand_name} {model_name}")
    # Evita redundância se brand já está no model (ex: "Abarth Abarth 695")
    if brand_name.lower() not in model_name.lower():
        queries_to_try.append(model_name)

    for query in queries_to_try:
        search_params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": 10,
            "prop": "imageinfo",
            "iiprop": "url|mime",
            "iiurlwidth": 1000,
            "format": "json",
        }
        try:
            res = requests.get(search_url, params=search_params, headers=headers, timeout=10)
            if res.status_code != 200:
                continue
            data = res.json()
            pages = data.get("query", {}).get("pages", {})
            if not pages:
                print(f"   [Commons] Nenhum resultado para query: '{query}'", flush=True)
                continue

            pages_list = sorted(pages.values(), key=lambda x: x.get("index", 999))
            print(f"   [Commons] Query '{query}': {len(pages_list)} resultados", flush=True)

            for page_data in pages_list:
                title = page_data.get("title", "")
                if "imageinfo" not in page_data:
                    continue
                image_info = page_data["imageinfo"][0]
                url = image_info.get("thumburl") or image_info.get("url", "")
                mime = image_info.get("mime", "")
                url_lower = url.lower()

                # Verifica extensão/mime
                ext_ok = any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp'])
                mime_ok = any(t in mime for t in ['jpeg', 'png', 'webp'])
                if not ext_ok and not mime_ok:
                    print(f"   [Commons] Formato rejeitado ({mime}): {title}", flush=True)
                    continue

                # Verifica blacklist
                if _url_is_blacklisted(url, title):
                    print(f"   [Commons] Blacklist rejeitou: {title}", flush=True)
                    continue

                # Valida contexto automotivo no Commons
                title_lower = title.lower()
                vehicle_terms = ['car', 'truck', 'bus', 'vehicle', 'auto', 'van', 'suv', 'motorcycle', 'caminhão', 'carro', 'ônibus', 'tractor', 'trailer', 'coach', 'vw', 'volkswagen', 'chevrolet', 'ford', 'fiat', 'honda', 'toyota']
                is_safe = brand_name.lower() in title_lower
                if not is_safe:
                    for term in vehicle_terms:
                        if re.search(r'\b' + term + r'\b', title_lower):
                            is_safe = True
                            break
                if not is_safe:
                    print(f"   [Commons] Rejeitado por falta de contexto automotivo: {title}", flush=True)
                    continue

                # Valida aspect ratio
                try:
                    sample = requests.get(url, headers=headers, timeout=12, stream=True)
                    if sample.status_code != 200:
                        print(f"   [Commons] HTTP {sample.status_code} ao baixar: {url}", flush=True)
                        continue
                    img_content = b""
                    for chunk in sample.iter_content(chunk_size=8192):
                        img_content += chunk
                        if len(img_content) >= 204800:
                            break
                    sample.close()
                    if not _is_valid_car_image(img_content):
                        print(f"   [Commons] Aspecto inválido: {title}", flush=True)
                        continue
                    print(f"   [Commons] Válida: {title}", flush=True)
                    return url
                except Exception as e:
                    print(f"   [Commons] Erro ao validar '{title}': {e}", flush=True)
                    continue

        except Exception as e:
            print(f"   [Commons] Erro na requisição para '{query}': {e}", flush=True)

    return None


def fetch_and_save_car_photo_with_hashes(car_id, existing_hashes):
    """
    Busca e salva a URL da foto de um carro diretamente no campo `photo_url` (PostgreSQL).
    Estratégia:
      1. Wikipedia pageimages API (en + pt) — thumbnail do artigo, mais confiável
      2. Wikimedia Commons search — fallback para carros não cobertos pela Wikipedia
    Nenhum arquivo é baixado para o disco local.
    """
    from cars.models import Car
    try:
        car = Car.objects.select_related('brand').get(pk=car_id)
    except Car.DoesNotExist:
        return

    if car.photo or car.photo_url:
        return

    brand_name = car.brand.name
    model_name = car.model
    year = car.model_year or car.factory_year or ""
    headers = {"User-Agent": "CarrosBot/1.0 (cmsampaio71@gmail.com)"}

    # --- Estratégia 1: Wikipedia pageimages ---
    thumb_url = _fetch_wikipedia_thumbnail(brand_name, model_name, year, headers)
    if thumb_url:
        _try_save_photo_url(car, thumb_url, brand_name, model_name)
        return

    # --- Estratégia 2: Wikimedia Commons search ---
    commons_url = _fetch_commons_search(brand_name, model_name, year, headers)
    if commons_url:
        _try_save_photo_url(car, commons_url, brand_name, model_name)
        return

    print(f"   [Sem Foto] Nenhuma imagem válida encontrada para {brand_name} {model_name}", flush=True)





def fetch_and_save_car_photo(car_id):
    """
    Wrapper público para buscar fotos de um carro individual (usado pelos sinais).
    """
    existing_hashes = get_existing_photo_hashes()
    fetch_and_save_car_photo_with_hashes(car_id, existing_hashes)


def fix_all_photos():
    """
    Varre todos os carros, identifica duplicatas ou imagens quebradas/inexistentes,
    e baixa novas fotos exclusivas e válidas em segundo plano.
    Desconecta os sinais do Django durante o processo para evitar loop de threads.
    """
    from cars.signals import car_post_save
    from cars.models import Car
    from django.conf import settings

    post_save.disconnect(car_post_save, sender=Car)

    try:
        cars = list(Car.objects.select_related('brand').all())

        seen_hashes = {}
        duplicates = []
        broken_or_missing = []

        print(f"[{datetime.now()}] [Photo Cleanup] Iniciando varredura em {len(cars)} carros no banco de dados...")

        is_cloudinary = getattr(settings, 'DEFAULT_FILE_STORAGE', '') == 'cloudinary_storage.storage.MediaCloudinaryStorage'

        for car in cars:
            if car.photo:
                if is_cloudinary:
                    # Se estiver usando Cloudinary, assumimos que se a foto está cadastrada no banco, ela existe na nuvem.
                    # Isso evita baixar centenas de imagens a cada boot da imagem docker na nuvem.
                    if car.photo.name in seen_hashes:
                        duplicates.append(car)
                    else:
                        seen_hashes[car.photo.name] = car.id
                else:
                    try:
                        car.photo.open('rb')
                        content = car.photo.read()
                        car.photo.close()
                        if content:
                            img_hash = hashlib.md5(content).hexdigest()
                            if img_hash in seen_hashes:
                                duplicates.append(car)
                            else:
                                seen_hashes[img_hash] = car.id
                        else:
                            broken_or_missing.append(car)
                    except FileNotFoundError:
                        broken_or_missing.append(car)
                    except Exception:
                        broken_or_missing.append(car)
            else:
                broken_or_missing.append(car)

        existing_hashes = set(seen_hashes.keys()) if not is_cloudinary else set()
        to_fix = duplicates + broken_or_missing

        if not to_fix:
            print(f"[{datetime.now()}] [Photo Cleanup] Todos os carros possuem fotos válidas e exclusivas. Nada a fazer!")
            return

        print(f"[{datetime.now()}] [Photo Cleanup] Encontrados {len(duplicates)} duplicados e {len(broken_or_missing)} sem fotos/quebradas.")

        for car in to_fix:
            print(f"[{datetime.now()}] [Photo Cleanup] Reparando foto de {car.brand.name} {car.model} ({car.model_year or 'unknown'})...")
            car.photo = None
            car.save()
            fetch_and_save_car_photo_with_hashes(car.id, existing_hashes)

        print(f"[{datetime.now()}] [Photo Cleanup] Varredura e reparos finalizados com sucesso!")

    except Exception as e:
        print(f"[{datetime.now()}] [Photo Cleanup Error] Ocorreu um erro no processo de reparo: {e}")
    finally:
        post_save.connect(car_post_save, sender=Car)
        # Remove o arquivo de lock ao finalizar o processamento
        import tempfile
        lock_path = os.path.join(tempfile.gettempdir(), 'photo_cleanup.lock')
        try:
            os.remove(lock_path)
        except OSError:
            pass

