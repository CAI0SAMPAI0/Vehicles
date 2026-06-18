import os
import sys
import threading
from django.apps import AppConfig

class CarsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cars'

    def ready(self):
        import cars.signals
        
        # Avoid running multiple times in local development reloader
        run_main = os.environ.get('RUN_MAIN')
        is_runserver = 'runserver' in sys.argv
        
        if (is_runserver and run_main == 'true') or (not is_runserver):
            from cars.utils import fix_all_photos
            thread = threading.Thread(target=fix_all_photos)
            thread.daemon = True
            thread.start()