import os
import sys
import django

# Setup Django
backend_path = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from cars.models import Car
from cars.utils import _fetch_wikipedia_thumbnail, _fetch_commons_search, _try_save_photo_url

# Termos para identificar fotos ruins que já estão salvas
BAD_TERMS = ['SIG', 'Sauer', 'P320', 'map', 'flag', 'weapon', 'gun', 'pistol', 'city']

def fix_bad_photos():
    cars = Car.objects.exclude(photo_url__isnull=True)
    count = 0
    for car in cars:
        url = car.photo_url.lower() if car.photo_url else ""
        if any(term.lower() in url for term in BAD_TERMS) or ('scania' in car.brand.name.lower() and not 'scania' in url):
            print(f"Limpando foto suspeita do {car.brand.name} {car.model}...")
            
            # Limpa e tenta refetch
            car.photo = None
            car.photo_url = None
            car.save()
            count += 1
            
            brand = car.brand.name
            model = car.model
            year = car.model_year or car.factory_year or ""
            
            headers = {"User-Agent": "AutoDrive/1.0 (Contact: seu-email@exemplo.com)"}
            
            print(f"Buscando nova foto para {brand} {model}...")
            new_url = _fetch_wikipedia_thumbnail(brand, model, year, headers)
            if not new_url:
                new_url = _fetch_commons_search(brand, model, year, headers)
                
            if new_url:
                _try_save_photo_url(car, new_url, brand, model)
            else:
                print(f"Não encontrou nova foto para {brand} {model}")
                
    print(f"Processo concluído. {count} fotos foram corrigidas.")

if __name__ == "__main__":
    fix_bad_photos()
