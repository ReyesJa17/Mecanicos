import sqlite3
import os



import sqlite3


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
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ID_Encargado TEXT NOT NULL,
                Fecha_Entrada DATE NOT NULL,
                Status TEXT NOT NULL CHECK(Status IN ('liberated', 'in process', 'inactive')),
                Fecha_Salida DATE,
                ID_Camion TEXT,
                Motivo TEXT,
                Kilometraje_Entrada REAL NOT NULL
            );

            -- Table: Camion
            CREATE TABLE IF NOT EXISTS Camion (
                VIN TEXT PRIMARY KEY,
                NumeroUnidad INTEGER NOT NULL,
                Kilometraje REAL NOT NULL,
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

def create_orden_entrada(conn, id_encargado, fecha_entrada, status, id_camion, motivo, kilometraje_entrada):
    cursor = conn.cursor()
    query = """
    INSERT INTO Orden_Entrada (
        ID_Encargado, Fecha_Entrada, Status,
        Fecha_Salida, ID_Camion, Motivo, Kilometraje_Entrada
    ) VALUES (?, ?, ?, NULL, ?, ?, ?)
    """
    cursor.execute(query, (
        id_encargado, fecha_entrada, status,
        id_camion, motivo, kilometraje_entrada
    ))
    conn.commit()


def salida_orden_entrada(conn, orden_id, fecha_salida, status):
    """
    Updates the 'fecha_salida' and 'status' of an existing Orden_Entrada.

    Args:
        conn: Database connection.
        orden_id (int): ID of the order to update.
        fecha_salida (str): Exit date in 'YYYY-MM-DD' format.
        status (str): New status of the order ('liberated', 'in process', 'inactive').

    Returns:
        dict: A message indicating success or an error.
    """
    cursor = conn.cursor()
    try:
        # Validate status
        if status not in ('liberated', 'in process', 'inactive'):
            return {"error": "Invalid status value."}

        # Update the record
        query = """
        UPDATE Orden_Entrada
        SET Fecha_Salida = ?, Status = ?
        WHERE ID = ?
        """
        cursor.execute(query, (fecha_salida, status, orden_id))
        conn.commit()

        return {"message": "Orden_Entrada updated successfully."}
    except sqlite3.Error as e:
        return {"error": f"An error occurred: {e}"}


def read_orden_entrada(conn, orden_id):
    cursor = conn.cursor()
    query = "SELECT * FROM Orden_Entrada WHERE ID = ?"
    cursor.execute(query, (orden_id,))
    return cursor.fetchone()

def update_orden_entrada(conn, orden_id, id_encargado=None, fecha_entrada=None, status=None, fecha_salida=None, id_camion=None, motivo=None, kilometraje_entrada=None):
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
    if motivo is not None:
        fields.append("Motivo = ?")
        values.append(motivo)
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


#ORDEN ENTRADA WITH PRODUCTS AND CAMION

def create_order_with_products(conn, id_encargado, fecha_entrada, status, id_camion, motivo, kilometraje_entrada):
    """
    Creates a new Orden_Entrada, adds a Camion if it doesn't exist, and associates products with the order.

    Args:
        conn: Database connection.
        id_encargado (str): Identifier of the encargado (manager).
        fecha_entrada (str): Entry date in 'YYYY-MM-DD' format.
        status (str): Status of the order ('liberated', 'in process', 'inactive').
        id_camion (str): VIN of the truck.
        motivo (str): Reason for maintenance.
        kilometraje_entrada (float): Mileage upon entry.

    Returns:
        dict: A message indicating success or an error.
    """
    try:
        cursor = conn.cursor()

        # Check if the Camion exists
        cursor.execute("SELECT VIN FROM Camion WHERE VIN = ?", (id_camion,))
        camion = cursor.fetchone()

        if not camion:
            print(f"El camion con el VIN '{id_camion}' no se ha registrado")
            # Prompt user to enter Camion details
            print("Por favor proporciona los datos requeridos para su creacion:")
            numero_unidad = input("Numero Unidad: ")
            kilometraje = input("Kilometraje: ")
            marca = input("Marca: ")
            modelo = input("Modelo: ")

            # Convert Numero Unidad and Kilometraje to appropriate types
            try:
                numero_unidad = int(numero_unidad)
                kilometraje = float(kilometraje)
            except ValueError:
                return {"error": "Invalid input for Numero Unidad or Kilometraje."}

            # Create the new Camion
            create_camion(conn, id_camion, numero_unidad, kilometraje, marca, modelo)
            print(f"Camion con VIN '{id_camion}' ha sido creado.")

        # Create the Orden_Entrada
        create_orden_entrada(conn, id_encargado, fecha_entrada, status, id_camion, motivo, kilometraje_entrada)
        print("Orden_Entrada has been created.")

        # Retrieve the ID of the newly created order
        orden_id = cursor.lastrowid

        if not orden_id:
            # If lastrowid is not available, fetch the max ID
            cursor.execute("SELECT MAX(ID) FROM Orden_Entrada")
            orden_id = cursor.fetchone()[0]

        print("Por favor proporciona los ID de los productos usados en el servicio.")
        print("Enter 'finish' when you are done.")

        while True:
            product_input = input("Da el ID del producto (o 'finish' para terminar): ")
            if product_input.lower() == 'finish':
                break
            try:
                id_producto = int(product_input)

                # Validate that the product exists
                cursor.execute("SELECT ID, Nombre, Categoria FROM Productos WHERE ID = ?", (id_producto,))
                product = cursor.fetchone()
                if not product:
                    print(f"Product with ID {id_producto} does not exist. Please enter a valid Product ID.")
                    continue

                product_name = product[1]
                product_category = product[2]

                # Prompt for quantity
                cantidad_input = input(f"Selecciona la cantidad para '{product_name}' (Category: {product_category}): ")
                try:
                    cantidad = int(cantidad_input)
                    if cantidad <= 0:
                        print("La cantidad debe de ser entero positivo.")
                        continue
                except ValueError:
                    print("Cantidad Invalida.")
                    continue

                # Associate the product with the order via its ID
                result = create_productos_servicio(conn, orden_id, id_producto, cantidad)
                if 'error' in result:
                    print(result['error'])
                else:
                    print(result['message'])
            except ValueError:
                print("Product ID invalido. Please enter a valid integer.")

        return {"message": f"Order ID {orden_id} created successfully with associated products."}

    except sqlite3.Error as e:
        return {"error": f"An error occurred: {e}"}
    

#Create Products

def add_categories_and_products(conn, categories_and_products):
    """
    Adds categories and their associated products to the Productos table.

    Args:
        conn: Database connection.
        categories_and_products (list): List of dictionaries with 'category' and 'products' keys.
    """
    cursor = conn.cursor()
    try:
        for category_data in categories_and_products:
            category = category_data['category']
            products = category_data['products']
            for product_name in products:
                # Clean up product name (strip whitespace)
                product_name = product_name.strip()
                # Insert product into Productos table
                query = "INSERT INTO Productos (Nombre, Categoria) VALUES (?, ?)"
                cursor.execute(query, (product_name, category))
        conn.commit()
        print("Categories and products added successfully.")
    except sqlite3.Error as e:
        print(f"An error occurred while adding categories and products: {e}")




#Information queries

def get_products_used_in_order(conn, id_orden):
    cursor = conn.cursor()
    query = """
    SELECT p.Nombre, p.Categoria, ps.Cantidad
    FROM Productos_Servicio ps
    JOIN Productos p ON ps.ID_Producto = p.ID
    WHERE ps.ID_Orden = ?
    """
    cursor.execute(query, (id_orden,))
    return cursor.fetchall()



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

Requirements: Manager's ID, entry date, status, truck's VIN, maintenance reason, entry mileage.
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

Requirements: Order ID, exit date, status (should be updated to "liberated").
Use Case: Used by the manager to finalize an entrance order when service is completed. It records the exit date and changes the status to "liberated," indicating that the truck is ready for pickup.
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
Operation Details:

Entrance Order Creation:

Establishes a relationship with the specific shop branch.
Includes detailed truck information: unique identification (VIN) and odometer reading at entry.
Documents the manager responsible for the order.
Specifies the maintenance category:
Corrective: Addressing existing issues or malfunctions.
Preventive: Performing routine checks and services to prevent future problems.
Consumable: Replacing regularly depleted items, such as oil or filters.
Product and Consumable Tracking:

The entrance order is linked to a table listing all products and consumables used.
Vital for inventory management, ensuring all parts and materials are accounted for.
Order Status Management:

Each order has a status reflecting its current stage:
In Process: The truck is currently being serviced.
Inactive: The service is temporarily halted.
Liberated: The service is completed, and the truck is ready for pickup.
Mechanics update the entrance order with any additional information or status changes during maintenance.
Service Completion:

Upon completion, the manager registers the exit date and changes the status to "liberated."
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

