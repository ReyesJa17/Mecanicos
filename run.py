# Modifica tu run.py así:
import os
from web import create_app

env = os.environ.get('FLASK_ENV', 'development')
app = create_app(env)

if __name__ == '__main__':
    if os.name == 'nt':  # Windows
        app.run(host='0.0.0.0', port=5000, debug=True)
    else:  # Linux/Unix
        os.system(f'gunicorn --config gunicorn_config.py run:app')
