from flask import Flask, render_template
import pandas as pd
import sqlite3

app = Flask(__name__)

def get_data(query):
    try:
        # Conexión a la base de datos SQLite
        conn = sqlite3.connect('mecanicos.db')

        # Ejecutar la consulta SQL y cargar el resultado en un DataFrame
        df = pd.read_sql_query(query, conn)

        # Cerrar la conexión a la base de datos
        conn.close()

        return df

    except sqlite3.Error as e:
        print(f"Error al conectar o consultar la base de datos: {e}")
        return None

@app.route('/')
def index():
    query = "SELECT * FROM tu_tabla"  # Tu consulta SQL aquí
    data = get_data(query)

    if data is None or data.empty:
        return "No se encontraron datos para mostrar."

    # Convertir el DataFrame a una lista de diccionarios para pasarlo a la plantilla
    data_dict = data.to_dict(orient='records')

    return render_template('table.html', data=data_dict)

if __name__ == '__main__':
    app.run(debug=True)