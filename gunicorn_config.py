import multiprocessing
import os

# Configuración de workers
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2

# Configuración de binding
bind = '0.0.0.0:5000'

# Configuración de timeout
timeout = 120

# Configuración de logging
accesslog = 'access.log'
errorlog = 'error.log'
loglevel = 'info'

# Configuración de worker_class
worker_class = 'gevent'

# Configuración de environment
raw_env = [
    f'FLASK_ENV=production',
    f'DATABASE_PATH={os.path.abspath("database/mecanicos.db")}'
]