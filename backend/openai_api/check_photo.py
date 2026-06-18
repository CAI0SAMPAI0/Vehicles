import os
import sys
from dotenv import load_dotenv

backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dotenv_path = os.path.join(backend_path, '.env')
load_dotenv(dotenv_path)
if backend_path not in sys.path:
    sys.path.append(backend_path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
import django
django.setup()

from cars.models import Car
from django.conf import settings

def main():
    print("DEFAULT_FILE_STORAGE in settings:", settings.DEFAULT_FILE_STORAGE)
    print("CLOUDINARY_CLOUD_NAME in settings:", settings.CLOUDINARY_STORAGE.get('CLOUD_NAME') if hasattr(settings, 'CLOUDINARY_STORAGE') else None)
    print("CLOUDINARY_CLOUD_NAME in env:", os.getenv("CLOUDINARY_CLOUD_NAME"))
    
    # Pega um carro que foi atualizado e tem foto cadastrada
    cars = Car.objects.filter(photo__isnull=False).exclude(photo="")
    
    output_lines = []
    output_lines.append(f"Encontrados {cars.count()} carros com foto no banco.")
    
    for car in cars[:10]:
        output_lines.append(f"\nCarro ID: {car.id} - {car.brand.name} {car.model}")
        output_lines.append(f"  photo field value: {car.photo}")
        output_lines.append(f"  photo.name: {car.photo.name}")
        try:
            output_lines.append(f"  photo.url: {car.photo.url}")
        except Exception as e:
            output_lines.append(f"  photo.url error: {e}")
            
    # Escreve o resultado no arquivo debug
    debug_file = os.path.join(backend_path, "photo_debug.txt")
    with open(debug_file, "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    print(f"Debug concluído! Resultados salvos em: {debug_file}")

if __name__ == '__main__':
    main()
