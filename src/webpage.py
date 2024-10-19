from flask import Flask, render_template
import pandas as pd
import sqlite3
import os

# Obtener la ruta absoluta del directorio actual (donde está este script)
script_dir = os.path.dirname(os.path.abspath(__file__))

# Ruta a la base de datos
DATABASE_PATH = os.path.join(os.path.dirname(script_dir), 'mecanicos.db')

# Crear la aplicación Flask y especificar la carpeta de plantillas
app = Flask(__name__, template_folder=os.path.join(script_dir, 'templates'))

def get_combined_data():
    try:
        conn = sqlite3.connect(DATABASE_PATH)

        # Consulta SQL modificada
        query = """
        SELECT 
            c.Marca AS MARCA,
            c.Modelo AS MODELO,
            c.VIN AS VIN,
            c.NumeroUnidad AS NUMERO_UNIDAD,
            oe.Fecha_Entrada AS FECHA_ENTRADA_ORDEN,
            oe.ID AS ID_ORDEN_ENTRADA,
            oe.Tipo AS TIPO_MANTENIMIENTO,
            oe.Status AS STATUS,
            GROUP_CONCAT(DISTINCT p.Categoria) AS CATEGORIA_PRODUCTOS,
            GROUP_CONCAT(p.Nombre || ' x' || ps.Cantidad, '||') AS Productos_Servicio,
            c.Kilometraje AS KILOMETRAJE,
            oe.Fecha_Salida AS FECHA_SALIDA_ORDEN
        FROM Orden_Entrada oe
        JOIN Camion c ON oe.ID_Camion = c.VIN
        JOIN Productos_Servicio ps ON oe.ID = ps.ID_Orden
        JOIN Productos p ON ps.ID_Producto = p.ID
        GROUP BY oe.ID
        ORDER BY oe.Fecha_Entrada DESC;
        """

        # Ejecutar la consulta y obtener el DataFrame
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Formatear 'Productos_Servicio' como una lista con viñetas
        def format_product_list(product_str):
            items = product_str.split('||')
            # Crear una lista HTML con viñetas
            return '<ul style="text-align: left;">' + ''.join([f'<li>{item.strip()}</li>' for item in items]) + '</ul>'

        df['Productos_Servicio'] = df['Productos_Servicio'].apply(format_product_list)

        # Reordenar las columnas para que 'Productos_Servicio' venga antes de 'FECHA_SALIDA_ORDEN'
        columns_order = [
            'MARCA', 'MODELO', 'VIN', 'NUMERO_UNIDAD', 'FECHA_ENTRADA_ORDEN',
            'ID_ORDEN_ENTRADA', 'TIPO_MANTENIMIENTO', 'STATUS',
            'CATEGORIA_PRODUCTOS', 'Productos_Servicio', 'KILOMETRAJE', 'FECHA_SALIDA_ORDEN'
        ]
        df = df[columns_order]

        return df
    except sqlite3.Error as e:
        print(f"Error al conectar o consultar la base de datos: {e}")
        return None

@app.route('/')
def index():
    data = get_combined_data()

    if data is None:
        return "Error al obtener los datos de la base de datos."

    if data.empty:
        return "No se encontraron datos para mostrar."

    # Convertir el DataFrame a HTML con estilos de Bootstrap
    table_html = data.to_html(
        classes='table table-bordered table-striped',
        index=False,
        justify='center',
        escape=False
    )

    return render_template('index.html', table_html=table_html)

if __name__ == '__main__':
    # Imprimir información para depuración
    print("Directorio actual de trabajo:", os.getcwd())
    print("Directorio del script:", script_dir)
    print("Carpeta de plantillas:", app.template_folder)
    print("Ruta de la base de datos:", DATABASE_PATH)

    app.run(debug=True)
