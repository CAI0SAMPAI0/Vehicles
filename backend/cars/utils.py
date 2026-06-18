import os
import hashlib
import requests
from django.core.files.base import ContentFile

def get_existing_photo_hashes():
    """
    Computes and returns a set of MD5 hashes of all existing car photos.
    """
    hashes = set()
    from cars.models import Car
    for car in Car.objects.exclude(photo='').exclude(photo__isnull=True):
        try:
            if car.photo:
                # Open and read the image content
                car.photo.open('rb')
                content = car.photo.read()
                car.photo.close()
                if content:
                    file_hash = hashlib.md5(content).hexdigest()
                    hashes.add(file_hash)
        except Exception as e:
            print(f"Error hashing photo for car {car.id}: {e}")
    return hashes

def fetch_and_save_car_photo(car_id):
    """
    Searches Wikimedia Commons for a unique photo of the car.
    Checks the MD5 hash of downloaded candidates against existing car photos.
    Saves the first unique match.
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
        f"{brand_name} {model_name} {year} car",
        f"{brand_name} {model_name} car",
        f"{brand_name} {model_name}",
    ]

    headers = {"User-Agent": "CarrosBot/1.0 (cmsampaio71@gmail.com)"}
    search_url = "https://commons.wikimedia.org/w/api.php"

    existing_hashes = get_existing_photo_hashes()

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
            res = requests.get(search_url, params=search_params, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                pages = data.get("query", {}).get("pages", {})
                if pages:
                    pages_list = list(pages.values())
                    pages_list.sort(key=lambda x: x.get("index", 999))

                    for page_data in pages_list:
                        title = page_data.get("title", "").lower()
                        if "imageinfo" in page_data:
                            image_info = page_data["imageinfo"][0]
                            url = image_info.get("thumburl") or image_info.get("url")

                            url_lower = url.lower()
                            if any(url_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                                if not any(x in url_lower or x in title for x in ["logo", "emblem", "badge", "drawing", "diagram", "interior", "sign"]):
                                    try:
                                        img_res = requests.get(url, headers=headers, timeout=15)
                                        if img_res.status_code == 200:
                                            img_content = img_res.content
                                            img_hash = hashlib.md5(img_content).hexdigest()
                                            
                                            # If this image content hash is already assigned to another car, skip it
                                            if img_hash in existing_hashes:
                                                print(f"   [Duplicate Detected] Hash {img_hash} already exists for another car. Skipping URL: {url}")
                                                continue
                                            
                                            # Unique image! Save it
                                            file_name = f"{brand_name}_{model_name}_{year}.jpg".replace(" ", "_").lower()
                                            car.photo.save(file_name, ContentFile(img_content), save=True)
                                            print(f"   [Success] Saved unique background image for {brand_name} {model_name} from: {url}")
                                            
                                            # Clear Redis/Django cache
                                            from django.core.cache import cache
                                            try:
                                                cache.clear()
                                            except Exception:
                                                pass
                                            return
                                    except Exception as e:
                                        print(f"Error downloading/checking image from {url}: {e}")
        except Exception as e:
            print(f"Error during Wikimedia request for query '{query}': {e}")
