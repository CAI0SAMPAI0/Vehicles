import io
import os
import hashlib
import requests
from django.core.files.base import ContentFile
from django.db.models.signals import post_save

# Termos proibidos no título ou URL da imagem (documentos, mapas, diagramas, logos, etc.)
PHOTO_BLACKLIST = [
    "logo", "emblem", "badge", "drawing", "diagram", "interior", "sign",
    "document", "map", "mapa", "text", "page", "pdf", "chart", "graph",
    "table", "scan", "record", "patent", "schematic", "blueprint", "brochure",
    "poster", "advertisement", "ad", "catalogue", "catalog", "flyer",
    "manual", "plan", "aerial", "satellite", "coat_of_arms", "flag",
    "icon", "symbol", "stamp", "label",
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
    """Verifica se a URL ou o título da imagem contém termos proibidos."""
    url_lower = url.lower()
    title_lower = title.lower()
    return any(term in url_lower or term in title_lower for term in PHOTO_BLACKLIST)


def fetch_and_save_car_photo_with_hashes(car_id, existing_hashes):
    """
    Função interna para buscar e baixar fotos reutilizando o conjunto de hashes fornecido.
    Aplica blacklist expandida e verificação de aspect ratio para evitar documentos/mapas.
    """
    from cars.models import Car
    try:
        car = Car.objects.select_related('brand').get(pk=car_id)
    except Car.DoesNotExist:
        return

    if car.photo:
        return

    brand_name = car.brand.name
    model_name = car.model
    year = car.model_year or car.factory_year or ""

    queries_to_try = [
        f"{brand_name} {model_name} {year} automóvel",
        f"{brand_name} {model_name} {year} car",
        f"{brand_name} {model_name} car",
        f"{brand_name} {model_name}",
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
            "gsrlimit": 8,
            "prop": "imageinfo",
            "iiprop": "url",
            "iiurlwidth": 1000,
            "format": "json"
        }

        try:
            res = requests.get(search_url, params=search_params, headers=headers, timeout=10)
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

                        # Aceita apenas formatos de imagem fotográfica
                        if not any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            continue

                        # Aplica blacklist de termos proibidos
                        if _url_is_blacklisted(url, title):
                            continue

                        try:
                            img_res = requests.get(url, headers=headers, timeout=15)
                            if img_res.status_code != 200:
                                continue

                            img_content = img_res.content

                            # Verifica aspect ratio (rejeita documentos portrait)
                            if not _is_valid_car_image(img_content):
                                print(f"   [Aspecto Inválido] Imagem rejeitada (documento/portrait): {url}")
                                continue

                            img_hash = hashlib.md5(img_content).hexdigest()

                            if img_hash in existing_hashes:
                                print(f"   [Foto Duplicada] Hash já cadastrado. Pulando: {url}")
                                continue

                            file_name = f"{brand_name}_{model_name}_{year}.jpg".replace(" ", "_").lower()
                            car.photo.save(file_name, ContentFile(img_content), save=True)
                            print(f"   [Sucesso] Imagem única salva para {brand_name} {model_name}: {url}")

                            existing_hashes.add(img_hash)

                            from django.core.cache import cache
                            try:
                                cache.clear()
                            except Exception:
                                pass
                            return

                        except Exception as e:
                            print(f"Erro ao baixar/validar imagem de {url}: {e}")

        except Exception as e:
            print(f"Erro na requisição ao Wikimedia para a busca '{query}': {e}")


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

    post_save.disconnect(car_post_save, sender=Car)

    try:
        cars = list(Car.objects.select_related('brand').all())

        seen_hashes = {}
        duplicates = []
        broken_or_missing = []

        print(f"[Photo Cleanup] Iniciando varredura em {len(cars)} carros no banco de dados...")

        for car in cars:
            if car.photo:
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

        existing_hashes = set(seen_hashes.keys())
        to_fix = duplicates + broken_or_missing

        if not to_fix:
            print("[Photo Cleanup] Todos os carros possuem fotos válidas e exclusivas. Nada a fazer!")
            return

        print(f"[Photo Cleanup] Encontrados {len(duplicates)} duplicados e {len(broken_or_missing)} sem fotos/quebradas.")

        for car in to_fix:
            print(f"[Photo Cleanup] Reparando foto de {car.brand.name} {car.model} ({car.model_year or 'unknown'})...")
            car.photo = None
            car.save()
            fetch_and_save_car_photo_with_hashes(car.id, existing_hashes)

        print("[Photo Cleanup] Varredura e reparos finalizados com sucesso!")

    except Exception as e:
        print(f"[Photo Cleanup Error] Ocorreu um erro no processo de reparo: {e}")
    finally:
        post_save.connect(car_post_save, sender=Car)
