# web/routes.py
from flask import Blueprint, render_template, request, Response
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from threading import Lock
import time
import logging
from sqlalchemy import text
from . import db  # Importa la instancia de la base de datos desde __init__.py

# Crear blueprint
main = Blueprint('main', __name__)

# Configuración de logging
logger = logging.getLogger(__name__)

# Variable global para tracking de modificaciones
last_modification = {
    'timestamp': 0,
    'lock': Lock()
}


def verify_database():
    """Verifica que la base de datos existe y tiene la estructura correcta"""
    try:
        # Obtener el motor de la base de datos
        engine = db.engine
        # Obtener los nombres de las tablas existentes
        inspector = db.inspect(engine)
        tables = inspector.get_table_names()
        required_tables = {'Productos', 'Orden_Entrada', 'Camion', 'Productos_Servicio'}
        existing_tables = set(tables)
        if not required_tables.issubset(existing_tables):
            logger.error(f"Faltan tablas en la base de datos. Tablas existentes: {existing_tables}")
            return False
        return True
    except Exception as e:
        logger.error(f"Error al verificar la base de datos: {e}")
        return False



def get_date_range(periodo):
    """
    Obtiene el rango de fechas basado en el periodo seleccionado.
    Retorna una tupla de (fecha_inicio, fecha_fin) en formato YYYY-MM-DD
    """
    today = datetime.now().date()
    
    if periodo == 'hoy':
        return today, today
    
    elif periodo == 'esta_semana':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
        return start_date, end_date
    
    elif periodo == 'este_mes':
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(day=31)
        else:
            next_month = today.replace(day=1, month=today.month + 1)
            end_date = next_month - timedelta(days=1)
        return start_date, end_date
    
    return None, None

def normalize_lugar(lugar):
    """Normaliza el nombre del lugar para coincidir con la base de datos"""
    lugar_map = {
        'VILLA_HERMOSA': 'VILLA HERMOSA',
        'VILLAHERMOSA': 'VILLA HERMOSA',
        'VILLA HERMOSA': 'VILLA HERMOSA'
    }
    lugar = lugar.upper().replace('_', ' ')
    return lugar_map.get(lugar.replace(' ', ''), lugar)

# Función para obtener la última modificación de la base de datos
def get_database_modification_time():
    """Obtiene el timestamp de la última modificación en la base de datos"""
    try:
        # Realiza una consulta para obtener la última fecha de modificación en 'Orden_Entrada'
        query = text("SELECT GREATEST(MAX(Fecha_Entrada), MAX(Fecha_Salida)) AS last_mod_time FROM Orden_Entrada")
        result = db.session.execute(query).fetchone()

        if result and result['last_mod_time']:
            return result['last_mod_time'].timestamp()
        else:
            return 0
    except Exception as e:
        logger.error(f"Error al obtener la hora de modificación de la base de datos: {e}")
        return 0
    
# Función para verificar actualizaciones
def check_for_updates():
    """Verifica si hay actualizaciones en la base de datos"""
    try:
        current_mod_time = get_database_modification_time()
        with last_modification['lock']:
            if current_mod_time > last_modification['timestamp']:
                last_modification['timestamp'] = current_mod_time
                return True
        return False
    except Exception as e:
        logger.error(f"Error al verificar actualizaciones: {e}")
        return False
    
def get_table_html(lugar, estado=None, periodo=None):
    """Genera el HTML de la tabla con los datos filtrados para MySQL"""
    try:
        lugar = normalize_lugar(lugar)
        logger.debug(f"Buscando datos para lugar: {lugar}")

        query = """
        SELECT 
            oe.ID_Entrada AS "ID Orden",
            DATE_FORMAT(oe.Fecha_Entrada, '%Y-%m-%d') AS "Fecha de Entrada",
            DATE_FORMAT(oe.hora_registro, '%H:%i') AS "Hora de Entrada",


            c.VIN AS "VIN",
            c.Modelo AS "Modelo",
            c.Marca AS "Marca",
            oe.Motivo_Entrada AS "Motivo de Entrada",
            oe.Tipo AS "Tipo de Mantenimiento",
            UPPER(oe.Status) AS "Estado",
            GROUP_CONCAT(DISTINCT p.Categoria) AS "Categorías",
            GROUP_CONCAT(
                CONCAT(
                    COALESCE(p.Nombre, 'Sin productos'),
                    COALESCE(CONCAT(' x', ps.Cantidad), '')
                ) SEPARATOR '||'
            ) AS "Productos y Cantidades",
            CAST(oe.Kilometraje AS UNSIGNED) AS "Kilometraje",

            oe.Motivo_Salida AS "Motivo de Salida",
            COALESCE(DATE_FORMAT(oe.Fecha_Salida, '%Y-%m-%d'), 'Pendiente') AS "Fecha de Salida",

            COALESCE(DATE_FORMAT(oe.hora_salida, '%H:%i'), 'Pendiente') AS "Hora de Salida"

        FROM Orden_Entrada oe
        LEFT JOIN Camion c ON oe.ID_Camion = c.VIN
        LEFT JOIN Productos_Servicio ps ON oe.ID_Entrada = ps.ID_Orden
        LEFT JOIN Productos p ON ps.ID_Producto = p.ID
        WHERE oe.Lugar = :lugar
        """

        params = {'lugar': lugar}

        if estado and estado != 'todos':
            query += " AND LOWER(oe.Status) = LOWER(:estado)"
            params['estado'] = estado

        if periodo and periodo != 'todos':
            start_date, end_date = get_date_range(periodo)
            if start_date and end_date:
                query += " AND DATE(oe.Fecha_Entrada) BETWEEN :start_date AND :end_date"
                params['start_date'] = start_date.strftime('%Y-%m-%d')
                params['end_date'] = end_date.strftime('%Y-%m-%d')

        query += " GROUP BY oe.ID_Entrada ORDER BY oe.Fecha_Entrada DESC, oe.hora_registro DESC"

        logger.debug(f"Query: {query}")
        logger.debug(f"Params: {params}")

        # Ejecutar la consulta y obtener los resultados
        result = db.session.execute(text(query), params)

        # Convertir el resultado en una lista de diccionarios
        data = result.mappings().all()
        logger.debug(f"Data retrieved from database: {data}")

        if not data:
            return f'<div class="alert alert-info">No se encontraron registros para {lugar} con los filtros aplicados.</div>'

        # Crear el DataFrame a partir de la lista de diccionarios
        df = pd.DataFrame(data)
        logger.debug(f"DataFrame creado con columnas: {df.columns.tolist()}")

        # Rellenar valores nulos de 'Kilometraje' con 0 y convertir a enteros
        df['Kilometraje'] = df['Kilometraje'].fillna(0).astype(int)
        # Definir funciones de formateo
        def format_product_list(product_str):
            if pd.isna(product_str):
                return '<ul class="product-list"><li>Sin productos registrados</li></ul>'
            items = product_str.split('||')
            if not items or items[0] == '':
                return '<ul class="product-list"><li>Sin productos registrados</li></ul>'
            return '<ul class="product-list">' + ''.join([f'<li>{item.strip()}</li>' for item in items if item.strip()]) + '</ul>'

        def format_status(status):
            if pd.isna(status):
                return '<strong class="estado-pendiente">NO ESPECIFICADO</strong>'
            status = status.lower()
            status_class = {
                'liberada': 'estado-completado',
                'proceso': 'estado-en-proceso',
                'inactiva': 'estado-pendiente'
            }.get(status, 'estado-pendiente')
            status_display = {
                'liberada': 'LIBERADA',
                'proceso': 'EN PROCESO',
                'inactiva': 'INACTIVA'
            }.get(status, status.upper())
            return f'<strong class="{status_class}">{status_display}</strong>'

        # Formatear columnas especiales
        df['ID Orden'] = df['ID Orden'].apply(lambda x: f'<strong>{x}</strong>')
        df['Estado'] = df['Estado'].apply(format_status)

        # Rellenar valores nulos
        df = df.fillna({
            'Marca': 'No especificado',
            'Modelo': 'No especificado',
            'VIN': 'No especificado',
            'Tipo de Mantenimiento': 'No especificado',
            'Estado': 'PENDIENTE',
            'Categorías': 'No especificado',
            'Kilometraje': 0,
            'Motivo de Entrada': 'No especificado',
            'Motivo de Salida': 'No especificado',
            'Hora de Entrada': 'No especificado',
            'Hora de Salida': 'Pendiente'
        })

        # Formatear lista de productos
        df['Productos y Cantidades'] = df['Productos y Cantidades'].apply(format_product_list)

        # Ordenar columnas
        columns_order = [
            'ID Orden', 'Fecha de Entrada', 'Hora de Entrada', 'VIN', 'Modelo',
            'Marca', 'Motivo de Entrada', 'Tipo de Mantenimiento', 'Estado',
            'Categorías', 'Productos y Cantidades', 'Kilometraje', 'Motivo de Salida',
            'Fecha de Salida', 'Hora de Salida'
        ]
        df = df[columns_order]

        # Convertir DataFrame a HTML
        table_html = df.to_html(
            classes='table table-bordered table-striped table-hover table-responsive',
            index=False,
            justify='center',
            escape=False
        )

        return table_html

    except Exception as e:
        logger.error(f"Error general: {e}")
        return f'<div class="alert alert-danger">Error inesperado: {str(e)}</div>'

@main.route('/')
def index():
    """Ruta principal"""
    return render_template('index.html')

@main.route('/tabla/<lugar>')
def tabla(lugar):
    """Ruta para obtener la tabla filtrada"""
    try:
        logger.info(f"Recibida petición para lugar: {lugar}")
        estado = request.args.get('estado', 'todos')
        periodo = request.args.get('periodo', 'todos')
        logger.info(f"Filtros - Estado: {estado}, Periodo: {periodo}")
        
        tabla_html = get_table_html(lugar, estado, periodo)
        if tabla_html is None:
            return "Error al obtener los datos de la base de datos.", 500
        return tabla_html
    except Exception as e:
        logger.error(f"Error en la ruta /tabla/{lugar}: {e}")
        return f"Error al procesar la solicitud: {str(e)}", 500



@main.errorhandler(404)
def page_not_found(e):
    """Manejador para errores 404"""
    return "Página no encontrada", 404

@main.errorhandler(500)
def internal_server_error(e):
    """Manejador para errores 500"""
    return "Error interno del servidor", 500



@main.route('/stream')
def stream():
    """Stream de eventos para actualizaciones en tiempo real"""
    def generate():
        lugar = request.args.get('lugar', '')
        estado = request.args.get('estado', 'todos')
        periodo = request.args.get('periodo', 'todos')
        
        while True:
            if check_for_updates(lugar, estado, periodo):
                try:
                    tabla_html = get_table_html(lugar, estado, periodo)
                    data = {
                        'html': tabla_html,
                        'timestamp': datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                except Exception as e:
                    logging.error(f"Error al generar actualización: {e}")
            time.sleep(2)

    return Response(generate(), mimetype='text/event-stream')

@main.route('/health')
def health():
    return 'OK', 200
