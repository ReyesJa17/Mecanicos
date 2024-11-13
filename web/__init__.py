# web/__init__.py
from flask import Flask
from .config import config
import logging
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()  # Crea la instancia de la base de datos aquí

def create_app(config_name='default'):
    """Application factory para Flask"""
    app = Flask(__name__)

    # Cargar configuración
    app.config.from_object(config[config_name])

    # Inicializar la base de datos
    db.init_app(app)

    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('app.log'),
            logging.StreamHandler()
        ]
    )

    # Registrar blueprints
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
