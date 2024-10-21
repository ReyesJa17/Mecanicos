import sqlite3
import os
import pandas as pd


# Path to the SQLite database file
db_path = 'mecanicos.db'


#Initialize database
def initialize_database(db_path: str):
    """
    Initializes the SQLite database with the provided schema.
    Checks if the database file already exists.

    Args:
        db_path (str): The path to the SQLite database file.
    """
    try:
        if os.path.exists(db_path):
            print(f"The database '{db_path}' already exists.")
            return
        else:
            # Connect to the SQLite database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys = ON;")

            # SQL script to create the tables
            sql_script = """
            -- Table: Productos
            CREATE TABLE IF NOT EXISTS Productos (
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                Nombre TEXT NOT NULL,
                Categoria TEXT NOT NULL
            );

            -- Table: Orden_Entrada
            CREATE TABLE IF NOT EXISTS Orden_Entrada (
                ID INTEGER PRIMARY KEY NOT NULL,
                ID_Encargado TEXT NOT NULL,
                Fecha_Entrada DATE NOT NULL,
                Status TEXT NOT NULL CHECK(Status IN ('liberada', 'proceso', 'inactiva')),
                Fecha_Salida DATE,
                ID_Camion TEXT,
                Motivo_Entrada TEXT,
                Motivo_Salida TEXT,
                Tipo TEXT CHECK(Tipo IN ('CONSUMIBLE', 'PREVENTIVO', 'CORRECTIVO')),
                Kilometraje_Entrada INTEGER NOT NULL
            );

            -- Table: Camion
            CREATE TABLE IF NOT EXISTS Camion (
                VIN TEXT PRIMARY KEY,
                NumeroUnidad INTEGER NOT NULL,
                Kilometraje INTEGER NOT NULL,
                Marca TEXT NOT NULL,
                Modelo TEXT NOT NULL
            );

            -- Table: Productos_Servicio
            CREATE TABLE IF NOT EXISTS Productos_Servicio (
                ID_Orden INTEGER NOT NULL,
                ID_Producto INTEGER NOT NULL,
                Cantidad INTEGER NOT NULL,
                PRIMARY KEY (ID_Orden, ID_Producto),
                FOREIGN KEY (ID_Orden) REFERENCES Orden_Entrada(ID),
                FOREIGN KEY (ID_Producto) REFERENCES Productos(ID)
            );
            """

            # Execute the script
            cursor.executescript(sql_script)

            # Commit the changes
            conn.commit()

            print(f"Database '{db_path}' initialized successfully!")

    except sqlite3.Error as e:
        print(f"An error occurred while initializing the database: {e}")

    except Exception as ex:
        print(f"An unexpected error occurred: {ex}")

    finally:
        # Close the connection
        if 'conn' in locals():
            conn.close()


# Usage example
# initialize_database("your_database.db")





#Camion


def create_camion(conn, vin, numero_unidad, kilometraje, marca, modelo):
    cursor = conn.cursor()
    query = "INSERT INTO Camion (VIN, NumeroUnidad, Kilometraje, Marca, Modelo) VALUES (?, ?, ?, ?, ?)"
    cursor.execute(query, (vin, numero_unidad, kilometraje, marca, modelo))
    conn.commit()



def read_camion(conn, vin):
    cursor = conn.cursor()
    query = "SELECT * FROM Camion WHERE VIN = ?"
    cursor.execute(query, (vin,))
    return cursor.fetchone()


def update_camion(conn, vin, numero_unidad=None, kilometraje=None, marca=None, modelo=None):
    cursor = conn.cursor()
    fields = []
    values = []

    if numero_unidad is not None:
        fields.append("NumeroUnidad = ?")
        values.append(numero_unidad)
    if kilometraje is not None:
        fields.append("Kilometraje = ?")
        values.append(kilometraje)
    if marca is not None:
        fields.append("Marca = ?")
        values.append(marca)
    if modelo is not None:
        fields.append("Modelo = ?")
        values.append(modelo)

    if not fields:
        return {"error": "No fields to update."}

    values.append(vin)
    query = f"UPDATE Camion SET {', '.join(fields)} WHERE VIN = ?"
    cursor.execute(query, values)
    conn.commit()

    return {"message": "Camion updated successfully."}


def delete_camion(conn, vin):
    cursor = conn.cursor()
    query = "DELETE FROM Camion WHERE VIN = ?"
    cursor.execute(query, (vin,))
    conn.commit()



#Productos_Servicio
def create_productos_servicio(conn, id_orden, id_producto, cantidad):
    cursor = conn.cursor()
    try:
        # Ensure the product exists
        cursor.execute("SELECT ID FROM Productos WHERE ID = ?", (id_producto,))
        if not cursor.fetchone():
            return {"error": f"Product with ID {id_producto} does not exist."}

        # Insert into Productos_Servicio
        query = "INSERT INTO Productos_Servicio (ID_Orden, ID_Producto, Cantidad) VALUES (?, ?, ?)"
        cursor.execute(query, (id_orden, id_producto, cantidad))
        conn.commit()
        return {"message": f"Product ID {id_producto} associated with Order ID {id_orden} (Quantity used: {cantidad})."}
    except sqlite3.IntegrityError as e:
        return {"error": f"Failed to associate product with service: {e}"}
    except sqlite3.Error as e:
        return {"error": f"An error occurred: {e}"}

def read_productos_servicio(conn, id_orden):
    cursor = conn.cursor()
    query = """
    SELECT ps.ID_Orden, ps.ID_Producto, p.Nombre, p.Categoria, p.Cantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    WHERE ps.ID_Orden = ?
    """
    cursor.execute(query, (id_orden,))
    return cursor.fetchall()


def delete_productos_servicio(conn, id_orden, id_producto):
    cursor = conn.cursor()
    query = "DELETE FROM Productos_Servicio WHERE ID_Orden = ? AND ID_Producto = ?"
    cursor.execute(query, (id_orden, id_producto))
    conn.commit()
    return {"message": "Product removed from service successfully."}

def update_productos_servicio(conn, id_orden, id_producto, new_id_orden=None, new_id_producto=None):
    cursor = conn.cursor()
    fields = []
    values = []

    if new_id_orden is not None:
        fields.append("ID_Orden = ?")
        values.append(new_id_orden)
    if new_id_producto is not None:
        fields.append("ID_Producto = ?")
        values.append(new_id_producto)

    if not fields:
        return {"error": "No fields to update."}

    values.append(id_orden)
    values.append(id_producto)
    query = f"UPDATE Productos_Servicio SET {', '.join(fields)} WHERE ID_Orden = ? AND ID_Producto = ?"

    try:
        cursor.execute(query, values)
        conn.commit()
        return {"message": "Product-service association updated successfully."}
    except sqlite3.IntegrityError as e:
        return {"error": f"Failed to update Productos_Servicio: {e}"}

#Orden_Entrada

def create_orden_entrada(conn, orden_id: int, id_encargado: str, fecha_entrada: str, status: str, fecha_salida: str, id_camion: str, motivo_entrada: str, motivo_salida: str, tipo: str, kilometraje_entrada: int):
    """
    Crea una nueva Orden_Entrada en la base de datos.

    Args:
        conn: Conexión a la base de datos.
        orden_id (int): Identificador de la orden.
        id_encargado (str): Identificador del encargado.
        fecha_entrada (str): Fecha de entrada en formato 'YYYY-MM-DD'.
        status (str): Estado inicial de la orden.
        fecha_salida (str): Fecha de salida en formato 'YYYY-MM-DD'.
        id_camion (str): VIN del camión.
        motivo_entrada (str): Motivo de entrada.
        motivo_salida (str): Motivo de salida.
        tipo (str): Tipo de mantenimiento ('CONSUMIBLE', 'PREVENTIVO', 'CORRECTIVO').
        kilometraje_entrada (int): Kilometraje al entrar.

    Returns:
        dict: Mensaje de éxito o de error.
    """
    cursor = conn.cursor()

    try:
        query = """
        INSERT INTO Orden_Entrada (ID, ID_Encargado, Fecha_Entrada, Status, Fecha_Salida, ID_Camion, Motivo_Entrada, Motivo_Salida, Tipo, Kilometraje_Entrada)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (orden_id, id_encargado, fecha_entrada, status, fecha_salida, id_camion, motivo_entrada, motivo_salida, tipo, kilometraje_entrada))
        conn.commit()
        return {"message": "Orden de entrada creada exitosamente."}
    except sqlite3.Error as e:
        return {"error": f"Ocurrió un error al crear la orden de entrada: {e}"}


def salida_orden_entrada(conn, orden_id: int, fecha_salida: str, status: str, motivo_salida: str):
    """
    Actualiza la 'fecha_salida', 'status' y 'motivo_salida' de una Orden_Entrada existente.

    Args:
        conn: Conexión a la base de datos.
        orden_id (int): ID de la orden a actualizar.
        fecha_salida (str): Fecha de salida en formato 'YYYY-MM-DD'.
        status (str): Nuevo estado de la orden (debe ser 'liberada' o similar).
        motivo_salida (str): Motivo de salida.

    Returns:
        dict: Mensaje de éxito o de error.
    """
    cursor = conn.cursor()
    try:
        # Verificar si la orden existe
        cursor.execute("SELECT * FROM Orden_Entrada WHERE ID = ?", (orden_id,))
        orden = cursor.fetchone()
        if not orden:
            return {"error": f"No se encontró una orden con ID {orden_id}."}

        # Actualizar la orden con los nuevos datos
        query = """
        UPDATE Orden_Entrada
        SET Fecha_Salida = ?, Status = ?, Motivo_Salida = ?
        WHERE ID = ?
        """
        cursor.execute(query, (fecha_salida, status, motivo_salida, orden_id))
        conn.commit()
        return {"message": f"La orden con ID {orden_id} ha sido actualizada con fecha de salida y motivo de salida."}
    except sqlite3.Error as e:
        return {"error": f"Ocurrió un error al actualizar la orden: {e}"}



def read_orden_entrada(conn, orden_id):
    cursor = conn.cursor()
    query = "SELECT * FROM Orden_Entrada WHERE ID = ?"
    cursor.execute(query, (orden_id,))
    return cursor.fetchone()
def update_orden_entrada(conn, orden_id, id_encargado=None, fecha_entrada=None, status=None, fecha_salida=None, id_camion=None, motivo_entrada=None, motivo_salida=None, tipo=None, kilometraje_entrada=None):
    cursor = conn.cursor()

    # Update only the fields that are provided
    fields = []
    values = []

    if id_encargado is not None:
        fields.append("ID_Encargado = ?")
        values.append(id_encargado)
    if fecha_entrada is not None:
        fields.append("Fecha_Entrada = ?")
        values.append(fecha_entrada)
    if status is not None:
        fields.append("Status = ?")
        values.append(status)
    if fecha_salida is not None:
        fields.append("Fecha_Salida = ?")
        values.append(fecha_salida)
    if id_camion is not None:
        fields.append("ID_Camion = ?")
        values.append(id_camion)
    if motivo_entrada is not None:
        fields.append("Motivo_Entrada = ?")
        values.append(motivo_entrada)
    if motivo_salida is not None:
        fields.append("Motivo_Salida = ?")
        values.append(motivo_salida)
    if tipo is not None:
        fields.append("Tipo = ?")
        values.append(tipo)
    if kilometraje_entrada is not None:
        fields.append("Kilometraje_Entrada = ?")
        values.append(kilometraje_entrada)

    if not fields:
        return {"error": "No fields to update."}

    values.append(orden_id)
    query = f"UPDATE Orden_Entrada SET {', '.join(fields)} WHERE ID = ?"
    cursor.execute(query, values)
    conn.commit()

    return {"message": "Orden_Entrada updated successfully."}


def delete_orden_entrada(conn, orden_id):
    cursor = conn.cursor()

    # Check if the record exists
    query_check = "SELECT * FROM Orden_Entrada WHERE ID = ?"
    cursor.execute(query_check, (orden_id,))
    record = cursor.fetchone()

    if not record:
        return {"message": f"No record found with ID: {orden_id}"}

    # Delete the record
    query_delete = "DELETE FROM Orden_Entrada WHERE ID = ?"
    cursor.execute(query_delete, (orden_id,))
    conn.commit()

    return {"message": f"Orden_Entrada with ID: {orden_id} deleted successfully."}


#Producto
def create_producto(conn, nombre, cantidad, categoria):
    cursor = conn.cursor()
    query = "INSERT INTO Productos (Nombre, Cantidad, Categoria) VALUES (?, ?, ?)"
    cursor.execute(query, (nombre, cantidad, categoria))
    conn.commit()


def read_producto(conn, producto_id):
    cursor = conn.cursor()
    query = "SELECT * FROM Productos WHERE ID = ?"
    cursor.execute(query, (producto_id,))
    return cursor.fetchone()


def update_producto(conn, producto_id, nombre=None, cantidad=None, categoria=None):
    cursor = conn.cursor()
    fields = []
    values = []

    if nombre is not None:
        fields.append("Nombre = ?")
        values.append(nombre)
    if cantidad is not None:
        fields.append("Cantidad = ?")
        values.append(cantidad)
    if categoria is not None:
        fields.append("Categoria = ?")
        values.append(categoria)

    if not fields:
        return {"error": "No fields to update."}

    values.append(producto_id)
    query = f"UPDATE Productos SET {', '.join(fields)} WHERE ID = ?"
    cursor.execute(query, values)
    conn.commit()

    return {"message": "Producto updated successfully."}

def delete_producto(conn, producto_id):
    cursor = conn.cursor()
    query = "DELETE FROM Productos WHERE ID = ?"
    cursor.execute(query, (producto_id,))
    conn.commit()
import sqlite3
import json
import pika
from typing import Dict, Any



import sqlite3
from typing import Dict, Any, List

def create_order_with_products(
    conn: sqlite3.Connection,
    orden_id: int,
    id_encargado: str,
    fecha_entrada: str,
    status: str,
    id_camion: str,
    motivo_entrada: str,
    tipo: str,
    kilometraje_entrada: int,
    numero_unidad: int = None,
    camion_kilometraje: float = None,
    marca: str = None,
    modelo: str = None,
    productos: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Creates a new Orden_Entrada, adds a Camion if it doesn't exist, and associates products with the order.
    Receives user input through function arguments rather than RabbitMQ.

    Args:
        conn: Database connection.
        orden_id (int): ID of the order.
        id_encargado (str): Identifier of the encargado (manager).
        fecha_entrada (str): Entry date in 'YYYY-MM-DD' format.
        status (str): Status of the order ('liberada', 'proceso', 'inactiva').
        id_camion (str): VIN of the truck.
        motivo_entrada (str): Motivo de entrada.
        tipo (str): Tipo de mantenimiento ('CONSUMIBLE', 'PREVENTIVO', 'CORRECTIVO').
        kilometraje_entrada (int): Mileage upon entry.
        numero_unidad (int, optional): Número de unidad del camión.
        camion_kilometraje (float, optional): Kilometraje del camión.
        marca (str, optional): Marca del camión.
        modelo (str, optional): Modelo del camión.
        productos (list of dict, optional): Lista de productos a asociar con la orden.

    Returns:
        dict: A message indicating success or an error, along with the accumulated messages.
    """
    messages = []
    try:
        cursor = conn.cursor()

        # Check if the Camion exists
        cursor.execute("SELECT VIN FROM Camion WHERE VIN = ?", (id_camion,))
        camion = cursor.fetchone()

        if not camion:
            messages.append(f"El camión con el VIN '{id_camion}' no se ha registrado")
            
            # Ensure all inputs for creating a Camion are provided
            if not (numero_unidad and camion_kilometraje and marca and modelo):
                error_message = "Faltan datos para crear el camión."
                messages.append(error_message)
                return {"error": error_message, "messages": messages}

            # Create the new Camion
            create_camion(conn, id_camion, numero_unidad, camion_kilometraje, marca, modelo)
            messages.append(f"Camión con VIN '{id_camion}' ha sido creado.")

        # Check if orden_id is provided
        if not orden_id:
            error_message = "No se proporcionó un ID de orden válido."
            messages.append(error_message)
            return {"error": error_message, "messages": messages}

        fecha_salida = None
        motivo_salida = None
        # Create the Orden_Entrada
        create_orden_entrada(conn, orden_id, id_encargado, fecha_entrada, status, fecha_salida, id_camion, motivo_entrada, motivo_salida, tipo, kilometraje_entrada)
        messages.append("Orden de entrada ha sido creada.")

        # Associate products with the order if provided
        if productos:
            for product in productos:
                try:
                    id_producto = product.get('id_producto')
                    cantidad = product.get('cantidad')

                    # Validate that the product exists
                    cursor.execute("SELECT ID FROM Productos WHERE ID = ?", (id_producto,))
                    product_data = cursor.fetchone()
                    if not product_data:
                        messages.append(f"El producto con ID {id_producto} no existe. Por favor, ingresa un ID de producto válido.")
                        continue

                    if not cantidad or cantidad <= 0:
                        messages.append(f"La cantidad para el producto con ID {id_producto} debe ser un entero positivo.")
                        continue

                    # Associate the product with the order via its ID
                    result = create_productos_servicio(conn, orden_id, id_producto, cantidad)
                    messages.append(result.get('message', 'Producto agregado con éxito.'))
                except ValueError:
                    messages.append("ID de producto inválido. Por favor, ingresa un entero válido.")

        # Verification: Add verification messages to the list
        messages.append("--- Verificación de datos en las tablas ---")

        # Fetch and add Camion table contents
        cursor.execute("SELECT * FROM Camion WHERE VIN = ?", (id_camion,))
        camiones = cursor.fetchall()
        messages.append(f"Tabla 'Camion': {camiones}")

        # Fetch and add Orden_Entrada table contents
        cursor.execute("SELECT * FROM Orden_Entrada WHERE ID = ?", (orden_id,))
        ordenes = cursor.fetchall()
        messages.append(f"Tabla 'Orden_Entrada': {ordenes}")

        # Fetch and add Productos_Servicio table contents
        cursor.execute("SELECT * FROM Productos_Servicio WHERE ID_Orden = ?", (orden_id,))
        productos_servicio = cursor.fetchall()
        messages.append(f"Tabla 'Productos_Servicio': {productos_servicio}")

        # Fetch and add Productos table contents for associated products
        cursor.execute("""
            SELECT p.* FROM Productos p
            INNER JOIN Productos_Servicio ps ON p.ID = ps.ID_Producto
            WHERE ps.ID_Orden = ?
        """, (orden_id,))
        productos_asociados = cursor.fetchall()
        messages.append(f"Productos asociados en la tabla 'Productos': {productos_asociados}")

        return {"message": f"La orden con ID {orden_id} ha sido creada exitosamente con los productos asociados.", "messages": messages}

    except sqlite3.Error as e:
        error_message = f"Ocurrió un error: {e}"
        messages.append(error_message)
        return {"error": error_message, "messages": messages}

    finally:
        # Ensure the cursor is closed
        cursor.close()
        messages.append("Conexión a la base de datos cerrada correctamente.")


#Create Products
def add_categories_and_products(conn, categories_and_products):
    """
    Adds categories and their associated products to the Productos table with unique IDs.

    Args:
        conn: Database connection.
        categories_and_products (list): List of dictionaries with 'category' and 'products' keys.
    """
    cursor = conn.cursor()
    try:
        # Get the current maximum ID from Productos table
        cursor.execute("SELECT COALESCE(MAX(ID), 0) FROM Productos")
        product_id = cursor.fetchone()[0] + 1  # Start from the next available ID

        for category_data in categories_and_products:
            category = category_data['category']
            products = category_data['products']
            for product_name in products:
                # Clean up product name (strip whitespace)
                product_name = product_name.strip()
                # Insert product into Productos table with predefined ID
                query = "INSERT INTO Productos (ID, Nombre, Categoria) VALUES (?, ?, ?)"
                cursor.execute(query, (product_id, product_name, category))
                product_id += 1  # Increment ID for the next product

        conn.commit()
        print("Categories and products added successfully with predefined IDs.")
    except sqlite3.Error as e:
        print(f"An error occurred while adding categories and products: {e}")


#Information queries

def get_products_used_in_order(conn, id_orden):
    """
    Recupera y devuelve una lista de productos utilizados en una orden específica en formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        id_orden (int): ID de la orden.

    Returns:
        str: Una cadena de texto con los productos utilizados o un mensaje indicando que no se encontraron productos.
    """
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, ps.Cantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    WHERE ps.ID_Orden = ?
    """
    cursor.execute(query, (id_orden,))
    results = cursor.fetchall()
    
    if not results:
        return f"No se encontraron productos para la orden con ID {id_orden}."
    
    response = f"Productos utilizados en la orden {id_orden}:\n"
    for nombre, categoria, cantidad in results:
        response += f"- {nombre} (Categoría: {categoria}), Cantidad: {cantidad}\n"
    return response



def get_products_used_in_month(conn, year: int, month: int):
    """
    Recupera todos los productos utilizados y sus cantidades en todas las órdenes durante un mes específico, y los devuelve en un formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        year (int): Año de interés.
        month (int): Mes de interés (1-12).

    Returns:
        str: Una cadena de texto con los productos utilizados o un mensaje indicando que no se encontraron productos.
    """
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, SUM(ps.Cantidad) as TotalCantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    JOIN Orden_Entrada oe ON ps.ID_Orden = oe.ID
    WHERE strftime('%Y', oe.Fecha_Entrada) = ? AND strftime('%m', oe.Fecha_Entrada) = ?
    GROUP BY p.ID
    ORDER BY TotalCantidad DESC
    """
    cursor.execute(query, (str(year), f"{month:02d}"))
    results = cursor.fetchall()
    
    if not results:
        return f"No se encontraron productos utilizados en {month}/{year}."
    
    response = f"Productos utilizados en {month}/{year}:\n"
    for nombre, categoria, total_cantidad in results:
        response += f"- {nombre} (Categoría: {categoria}), Cantidad total: {total_cantidad}\n"
    return response


def get_products_used_in_month(conn, year: int, month: int):
    """
    Recupera todos los productos utilizados y sus cantidades en todas las órdenes durante un mes específico, y los devuelve en un formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        year (int): Año de interés.
        month (int): Mes de interés (1-12).

    Returns:
        str: Una cadena de texto con los productos utilizados o un mensaje indicando que no se encontraron productos.
    """
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, SUM(ps.Cantidad) as TotalCantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    JOIN Orden_Entrada oe ON ps.ID_Orden = oe.ID
    WHERE strftime('%Y', oe.Fecha_Entrada) = ? AND strftime('%m', oe.Fecha_Entrada) = ?
    GROUP BY p.ID
    ORDER BY TotalCantidad DESC
    """
    cursor.execute(query, (str(year), f"{month:02d}"))
    results = cursor.fetchall()
    
    if not results:
        return f"No se encontraron productos utilizados en {month}/{year}."
    
    response = f"Productos utilizados en {month}/{year}:\n"
    for nombre, categoria, total_cantidad in results:
        response += f"- {nombre} (Categoría: {categoria}), Cantidad total: {total_cantidad}\n"
    return response


def get_product_usage_for_truck(conn, vin: str, product_id: int, start_date: str, end_date: str):
    """
    Recupera la cantidad total de un producto específico utilizado en un camión determinado dentro de un rango de fechas, y la devuelve en formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        vin (str): VIN del camión.
        product_id (int): ID del producto.
        start_date (str): Fecha de inicio en formato 'YYYY-MM-DD'.
        end_date (str): Fecha de fin en formato 'YYYY-MM-DD'.

    Returns:
        str: Una cadena de texto con la cantidad total utilizada o un mensaje indicando que no se encontró uso del producto.
    """
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, SUM(ps.Cantidad) as TotalCantidad
    FROM Productos_Servicio ps
    JOIN Orden_Entrada oe ON ps.ID_Orden = oe.ID
    JOIN Productos p ON ps.ID_Producto = p.ID
    WHERE oe.ID_Camion = ? AND ps.ID_Producto = ?
      AND oe.Fecha_Entrada BETWEEN ? AND ?
    """
    cursor.execute(query, (vin, product_id, start_date, end_date))
    result = cursor.fetchone()
    
    if result and result[2]:
        nombre = result[0]
        categoria = result[1]
        total_cantidad = result[2]
        return (f"El producto '{nombre}' (Categoría: {categoria}) se utilizó {total_cantidad} "
                f"veces para el camión con VIN {vin} entre {start_date} y {end_date}.")
    else:
        return (f"No se encontró uso del producto con ID {product_id} para el camión con VIN {vin} "
                f"entre {start_date} y {end_date}.")



def get_products_used_for_truck(conn, vin: str):
    """
    Recupera todos los productos utilizados y sus cantidades para un camión específico, y los devuelve en un formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        vin (str): VIN del camión.

    Returns:
        str: Una cadena de texto con los productos utilizados o un mensaje indicando que no se encontraron productos.
    """
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, SUM(ps.Cantidad) as TotalCantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    JOIN Orden_Entrada oe ON ps.ID_Orden = oe.ID
    WHERE oe.ID_Camion = ?
    GROUP BY p.ID
    ORDER BY TotalCantidad DESC
    """
    cursor.execute(query, (vin,))
    results = cursor.fetchall()
    
    if not results:
        return f"No se encontraron productos utilizados para el camión con VIN {vin}."
    
    response = f"Productos utilizados para el camión con VIN {vin}:\n"
    for nombre, categoria, total_cantidad in results:
        response += f"- {nombre} (Categoría: {categoria}), Cantidad total: {total_cantidad}\n"
    return response


def get_order_count_for_branch(conn, sucursal: str):
    """
    Recupera el número de órdenes para una sucursal específica y lo devuelve en formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        sucursal (str): Nombre o identificador de la sucursal.

    Returns:
        str: Una cadena de texto con el número de órdenes o un mensaje indicando que no se encontraron órdenes.
    """
    cursor = conn.cursor()
    query = """
    SELECT COUNT(*) as OrderCount
    FROM Orden_Entrada
    WHERE Sucursal = ?
    """
    cursor.execute(query, (sucursal,))
    result = cursor.fetchone()
    count = result[0] if result else 0

    if count > 0:
        return f"La sucursal '{sucursal}' ha procesado {count} órdenes."
    else:
        return f"No se encontraron órdenes para la sucursal '{sucursal}'."


def get_order_details_for_truck(conn, vin: str):
    """
    Recupera las órdenes, motivos y fechas para un camión específico y las devuelve en un formato de texto legible.

    Args:
        conn: Conexión a la base de datos.
        vin (str): VIN del camión.

    Returns:
        str: Una cadena de texto con los detalles de las órdenes o un mensaje indicando que no se encontraron órdenes.
    """
    cursor = conn.cursor()
    query = """
    SELECT ID, Motivo, Fecha_Entrada
    FROM Orden_Entrada
    WHERE ID_Camion = ?
    ORDER BY Fecha_Entrada DESC
    """
    cursor.execute(query, (vin,))
    orders = cursor.fetchall()
    
    if not orders:
        return f"No se encontraron órdenes para el camión con VIN {vin}."
    
    response = f"Órdenes para el camión con VIN {vin}:\n"
    for order_id, motivo, fecha_entrada in orders:
        response += f"- Orden ID: {order_id}, Motivo: {motivo}, Fecha de Entrada: {fecha_entrada}\n"
    return response

#Excel Table

def export_orders_to_excel(db_path: str, excel_path: str):
    """
    Exporta campos específicos de la base de datos a un archivo de Excel utilizando pandas.
    Crea el archivo y su directorio si no existen.

    Args:
        db_path (str): Ruta al archivo de la base de datos SQLite.
        excel_path (str): Ruta donde se guardará el archivo de Excel.
    
    Returns:
        None
    """
    try:
        # Verificar si la base de datos existe
        if not os.path.exists(db_path):
            print(f"La base de datos en '{db_path}' no existe.")
            return

        # Asegurarse de que el directorio del archivo Excel exista
        directory = os.path.dirname(excel_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"Directorio '{directory}' creado para almacenar el archivo Excel.")

        # Conectar a la base de datos
        conn = sqlite3.connect(db_path)

        # Definir la consulta SQL con los joins necesarios
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
            p.Categoria AS CATEGORIA_PRODUCTOS,
            c.Kilometraje AS KILOMETRAJE,
            oe.Fecha_Salida AS FECHA_SALIDA_ORDEN
        FROM Orden_Entrada oe
        JOIN Camion c ON oe.ID_Camion = c.VIN
        JOIN Productos_Servicio ps ON oe.ID = ps.ID_Orden
        JOIN Productos p ON ps.ID_Producto = p.ID
        ORDER BY oe.Fecha_Entrada DESC
        """

        # Ejecutar la consulta y cargar los datos en un DataFrame de pandas
        df = pd.read_sql_query(query, conn)

        # Cerrar la conexión a la base de datos
        conn.close()

        # Verificar si el DataFrame está vacío
        if df.empty:
            print("No se encontraron datos para exportar.")
            return

        # Exportar el DataFrame a un archivo de Excel
        df.to_excel(excel_path, index=False)

        print(f"Datos exportados exitosamente a '{excel_path}'.")

    except sqlite3.Error as e:
        print(f"Error al conectar o consultar la base de datos: {e}")

    except Exception as ex:
        print(f"Ocurrió un error inesperado: {ex}")


#Informnation

mechanics_operation = """
The mechanic shop operates by receiving trucks that require various types of maintenance services. When a truck arrives at one of the shop's branches, the process begins with the manager creating an entrance order. This order is a critical document that captures all the essential information needed to service the truck effectively.

To facilitate this process, a suite of specialized tools has been incorporated into the shop's system. These tools streamline the creation and management of entrance orders, truck records, and product usage, ensuring that all data is accurately recorded and easily accessible.

Tools and Their Descriptions:

Create Camion Tool:

Requirements: VIN (Vehicle Identification Number), unit number, entry mileage, brand, and model.
Use Case: Used when a truck that is not yet in the system arrives at the shop. The manager inputs all necessary details about the truck to add it to the database, ensuring accurate maintenance records and future service planning.

Read Camion Tool:

Requirements: Truck's VIN.
Use Case: Allows staff to retrieve detailed information about a specific truck, ensuring the correct vehicle is associated with entrance orders and maintenance records.
Update Camion Tool:

Requirements: Truck's VIN and any details to be updated (unit number, mileage, brand, model).
Use Case: Used to update the truck's information in the database when changes occur, such as after servicing or correcting initial entry errors.

Delete Camion Tool:

Requirements: Truck's VIN.
Use Case: Removes a truck from the system, for example, if it is no longer in service or was entered incorrectly.

Create Order with Products Tool:

Requirements: Order ID, Manager's ID, entry date, status, truck's VIN, maintenance reason,type of maintenance, entry mileage.
Use Case: Used by the manager to create an entrance order when a truck arrives for service. This tool captures all essential order details and interactively queries the user to associate products and consumables used during the service.

Read Orden Entrada Tool:

Requirements: Order ID.
Use Case: Allows staff to view and verify the details of entrance orders, including associated products and services.

Update Orden Entrada Tool:

Requirements: Order ID and any details to be updated (status, additional services, etc.).
Use Case: Used to update the entrance order with new information, such as status changes or additional required maintenance.

Delete Orden Entrada Tool:

Requirements: Order ID.
Use Case: Removes an entrance order from the system, for instance, if it was created in error.

Salida Orden Entrada Tool:

Requirements: Order ID, exit date,exit motive, status (should be updated to "liberada").
Use Case: Used by the manager to finalize an entrance order when service is completed. It records the exit date and changes the status to "liberada," indicating that the truck is ready for pickup.

Read Producto Tool:

Requirements: Product ID.
Use Case: Retrieves information about a specific product or consumable used in services.

Update Producto Tool:

Requirements: Product ID and any details to be updated (name, category).
Use Case: Used to update product information in the database, such as correcting details or updating categories.

Delete Producto Tool:

Requirements: Product ID.
Use Case: Removes a product from the system, for example, if it has been discontinued.

Read Productos Servicio Tool:

Requirements: Order ID.
Use Case: Provides a detailed list of all products and consumables associated with a specific entrance order, aiding in inventory tracking and billing.


Get Products Used in Month Tool:

Requirements: Year, month.
Use case: Retrieves all products used and their quantities in all orders during a specific month. This helps monitor product usage trends and plan inventory replenishment.

Get Product Usage for Truck Tool:

Requirements: Truck VIN, product ID, start date, end date.
Use case: Retrieves the total quantity of a specific product used for a particular truck within a time range. Useful for detecting anomalies in product usage, which may indicate misuse or theft.

Get Products Used for Truck Tool:

Requirements: Truck VIN.
Use case: Retrieves all products used and their quantities for a specific truck in all orders. Helps review the maintenance history and verify product usage for that truck.

Get Order Count for Branch Tool:

Requirements: Branch name or identifier.
Use case: Retrieves the number of orders processed by a specific branch. This helps assess branch performance and manage workload distribution.

Get Order Details for Truck Tool:

Requirements: Truck VIN.
Use case: Retrieves the number of orders, reasons, and dates for a specific truck. Provides a complete view of the truck's service history, assisting in maintenance planning and communication with the customer.

Operation Details:

Entrance Order Creation:

Establishes a relationship with the specific shop branch.
Includes detailed truck information: unique identification (VIN) and odometer reading at entry.
Documents the manager responsible for the order.
Specifies the maintenance type:
Corrective: Addressing existing issues or malfunctions.
Preventive: Performing routine checks and services to prevent future problems.
Consumable: Replacing regularly depleted items, such as oil or filters.

Product and Consumable Tracking:

The entrance order is linked to a table listing all products and consumables used.
Vital for inventory management, ensuring all parts and materials are accounted for.
Order Status Management:

Each order has a status reflecting its current stage:
Proceso: The truck is currently being serviced.
Inactiva: The service is temporarily halted.
Liberada: The service is completed, and the truck is ready for pickup.
Mechanics update the entrance order with any additional information or status changes during maintenance.
Service Completion:

Upon completion, the manager registers the exit date and changes the status to "liberada."
Indicates the truck has been fully serviced and is ready to be returned to the customer.
By meticulously recording all this information and utilizing the integrated tools, the mechanic shop ensures a seamless operation that tracks every aspect of the service process. This comprehensive system allows for:

Efficient Workflow Management: Tools like the Create Order with Products Tool and Update Orden Entrada Tool streamline the service workflow, reducing errors and saving time.
Accurate Billing: Linking products and services directly to entrance orders enables precise invoicing based on actual materials used and work performed.
Inventory Control: Associating products with orders helps monitor stock levels and plan reorders.
Data for Future Reference: Detailed service records support future diagnostics and service planning.
Enhanced Customer Satisfaction: Ensures transparency and accountability throughout the maintenance service.
Guidelines for Assistance:

Data Collection: Always gather all required information before proceeding with any operation.
Data Validation: Ensure the accuracy of the provided data.
Persistence in Searching: If initial searches yield no results, expand your search parameters before concluding.
Maintain Data Integrity: Follow the mechanic shop's procedures and ensure data consistency.
Communication: Provide clear and precise responses to support efficient workshop management.
Language Preference: Always respond in Spanish.
"""

categories_and_products = [
    {
        "category": "Electrico",
        "products": [
            "Plafon",
            "Encendedor",
            "Luces",
            "Fallo electrico",
            "Corto",
            "Modulos",
            "Control de arranque",
            "Modulo de bomba",
            "Sensores",
            "Problemas en transmisión",
            "Adaptador de poste",
            "Modulo PSM",
            "Acumuladores tornillo",
            "Líneas traseras",
            "Calavera",
            "Sincronizador y alternador",
            "Juego de cornetas",
            "Pines",
            "Botonera",
            "Marcha",
            "Convertidor",
            "Arnes",
            "Cilindro e interruptor",
            "Bulbo",
            "Selenoide",
            "Sistema ABS",
            "Actualizacion de calibracion de modulo ECM"
        ]
    },
    {
        "category": "Motor",
        "products": [
            "MP",
            "Refrigerador de gases",
            "Códigos",
            "Cambio de catalizador",
            "Cambio de polea",
            "Filtro",
            "Batería",
            "Deja de acelerar",
            "Falla al encender",
            "Pérdidas de potencia",
            "Cambio de clutch",
            "Embrague",
            "Daño en Compresor",
            "Abrazaderas",
            "Radiador",
            "Bomba de agua",
            "Secador de aire",
            "Válvula e inyector",
            "Regeneración de postramiento",
            "Dosificador de urea",
            "Escape",
            "Banda",
            "Ajuste de velocidad",
            "Turbo",
            "Cambio de parámetro",
            "Bayoneta"
        ]
    },
    {
        "category": "Carrocería",
        "products": [
            "Patines",
            "Chasis",
            "Camas de madera",
            "Faldón",
            "Caja seca",
            "Puertas y herrajes",
            "Concha",
            "Abrazaderas",
            "Esquinero",
            "Cóncavo",
            "Escalón",
            "Fascia",
            "Faro",
            "Cofre",
            "Láminas",
            "Filtración",
            "Extensión de defensa",
            "Gasket",
            "Zócalo",
            "Defensa",
            "Lodera",
            "Estribo",
            "Parrilla",
            "Tablero",
            "Rampas",
            "Alerón"
        ]
    },
    {
        "category": "Suspensión",
        "products": [
            "Balero",
            "Amortiguadores",
            "Masa delantera",
            "Muelle rota/dañada",
            "Percha",
            "Pernos",
            "Horquilla",
            "Crucetas y baleros",
            "Soporte aleta de tiburón",
            "Terminal y brazo viajero",
            "Buje",
            "Albardones",
            "Se engrasa la quinta",
            "Barra estabilizadora"
        ]
    },
    {
        "category": "Frenos",
        "products": [
            "Reemplazo en cilindro esclavo",
            "Frenos",
            "Rotochamber",
            "Balatas",
            "Mangueras de aire",
            "Bolsa de aire",
            "Discos traseros",
            "Matraca",
            "Mangueras hidráulicas",
            "Fuga de aire",
            "Mangueras servicio"
        ]
    },
    {
        "category": "Tren motriz",
        "products": [
            "Chicote",
            "Sincronizador doble de 3A",
            "Palanca de velocidades",
            "Resorte de presión corona",
            "Gases",
            "Flecha",
            "Diferencial",
            "Cardán",
            "Transmisión Clutch"
        ]
    },
    {
        "category": "Dirección",
        "products": [
            "Llantas nuevas",
            "Birlos",
            "RIN",
            "Colocación de llantas",
            "Colocación de rin",
            "Talachas",
            "Alineación",
            "Balanceo"
        ]
    },
    {
        "category": "Fluidos",
        "products": [
            "Relleno de niveles",
            "Aceite",
            "Urea",
            "Anticongelante"
        ]
    }
]


#Create database

initialize_database('mecanicos.db')

conn = sqlite3.connect(db_path)

# Add categories and products
add_categories_and_products(conn, categories_and_products)

# Close the connection
conn.close()

