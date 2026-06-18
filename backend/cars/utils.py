import os
import hashlib
import requests
from django.core.files.base import ContentFile

def get_existing_photo_hashes():
    """
    Computes and returns a set of MD5 hashes of all existing valid car photos.
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
        except Exception as e:
            print(f"Error hashing photo for car {car.id}: {e}")
    return hashes

def fetch_and_save_car_photo_with_hashes(car_id, existing_hashes):
    """
    Internal photo search and download function that reuses a set of existing photo hashes.
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
                                            
                                            if img_hash in existing_hashes:
                                                print(f"   [Duplicate Detected] Hash {img_hash} already exists. Skipping URL: {url}")
                                                continue
                                            
                                            file_name = f"{brand_name}_{model_name}_{year}.jpg".replace(" ", "_").lower()
                                            car.photo.save(file_name, ContentFile(img_content), save=True)
                                            print(f"   [Success] Saved unique image for {brand_name} {model_name} from: {url}")
                                            
                                            existing_hashes.add(img_hash)
                                            
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

def fetch_and_save_car_photo(car_id):
    """
    Fetch image wrapper that retrieves the full set of hashes and requests a unique image.
    """
    existing_hashes = get_existing_photo_hashes()
    fetch_and_save_car_photo_with_hashes(car_id, existing_hashes)

def fix_all_photos():
    """
    Identifies all duplicate or broken photos in the database and updates them automatically.
    """
    from cars.models import Car
    try:
        cars = list(Car.objects.select_related('brand').all())
    except Exception as e:
        print(f"[Photo Cleanup Error] Could not list cars: {e}")
        return
    
    seen_hashes = {}
    duplicates = []
    broken_or_missing = []
    
    print(f"[Photo Cleanup] Scanning {len(cars)} cars in database for duplicates and missing photos...")
    
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
            except Exception:
                broken_or_missing.append(car)
        else:
            broken_or_missing.append(car)

    existing_hashes = set(seen_hashes.keys())
    to_fix = duplicates + broken_or_missing
    if not to_fix:
        print("[Photo Cleanup] All cars have unique, valid photos. Nothing to do!")
        return
        
    print(f"[Photo Cleanup] Found {len(duplicates)} duplicate photos and {len(broken_or_missing)} missing/broken photos to repair.")
    
    for car in to_fix:
        print(f"[Photo Cleanup] Repairing photo for {car.brand.name} {car.model} ({car.model_year or 'unknown'})...")
        car.photo = None
        car.save()
        fetch_and_save_car_photo_with_hashes(car.id, existing_hashes)
        
    print("[Photo Cleanup] Finished photo scanning and repairs successfully!")
