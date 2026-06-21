import os
import sys
import threading
from django.apps import AppConfig


class CarsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cars'

    def ready(self):
        import cars.signals
        
        # Only run the background loop thread when executing the actual web server 
        # (runserver or Gunicorn). Prevents it from running during collectstatic, migrate, etc.
        run_main = os.environ.get('RUN_MAIN')
        is_runserver = 'runserver' in sys.argv
        is_gunicorn = os.environ.get('SERVER_SOFTWARE', '').startswith('gunicorn')
        
        is_web_server = (is_runserver and run_main == 'true') or is_gunicorn
        
        if is_web_server:
            import tempfile
            import time
            lock_path = os.path.join(tempfile.gettempdir(), 'autodrive_worker.lock')
            
            acquire_lock = False
            if os.path.exists(lock_path):
                try:
                    with open(lock_path, 'r') as f:
                        pid_str = f.read().strip()
                        if pid_str.isdigit():
                            pid = int(pid_str)
                            try:
                                # os.kill(pid, 0) apenas checa se o processo existe
                                os.kill(pid, 0)
                            except OSError:
                                # Processo morreu, podemos deletar o lock antigo e pegar
                                acquire_lock = True
                        else:
                            acquire_lock = True
                except Exception:
                    acquire_lock = True
                    
                if acquire_lock:
                    try:
                        os.remove(lock_path)
                    except OSError:
                        pass
            else:
                acquire_lock = True
                
            if acquire_lock:
                try:
                    # Tenta criar o lock atomicamente
                    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    with os.fdopen(fd, 'w') as f:
                        f.write(str(os.getpid()))
                    
                    # Importa e inicia o background worker loop
                    from cars.worker import worker_loop
                    thread = threading.Thread(target=worker_loop)
                    thread.daemon = True
                    thread.start()
                    print(f"[Worker] Lock adquirido pelo PID {os.getpid()}. Worker iniciado.", flush=True)
                except FileExistsError:
                    pass
                except Exception as e:
                    print(f"[Worker Error] Falha ao iniciar worker: {e}", flush=True)