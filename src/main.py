from rabbit_connection import AsyncRabbitMQConsumer
import base64
from langchain_core.messages import AIMessage
import os
import asyncio
import datetime as dt
from langchain_core.runnables import RunnableLambda, Runnable, RunnableConfig
from datetime import datetime, date, timezone, timedelta
from langgraph.prebuilt import ToolNode
from langsmith import traceable
import logging
from typing import Optional, Union
from datetime import date, datetime
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated
from langchain_core.messages.tool import ToolMessage
from typing_extensions import TypedDict
from langchain_groq import ChatGroq
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from typing import Optional, Dict, Any, List
from typing import Optional, Union, List, Any
from datetime import datetime, date, timezone
import os.path
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.tools import tool

from langchain_core.messages import RemoveMessage
from utilsdb import (
    create_camion,
    create_orden_entrada,
    read_camion,
    update_camion,
    delete_camion,
    read_orden_entrada,
    update_orden_entrada,
    delete_orden_entrada,
    salida_orden_entrada,
    read_producto,
    update_producto,
    delete_producto,
    read_productos_servicio,
    mechanics_operation,
    get_products_used_in_month,
    get_product_usage_for_truck,
    get_products_used_for_truck,
    get_order_count_for_branch,
    get_order_details_for_truck,
    export_orders_to_excel,
    add_products_for_order,
)
import re
from langchain_core.runnables import ensure_config
from langchain_core.output_parsers import JsonOutputParser,  StrOutputParser
from langchain_core.messages import HumanMessage
from typing import Literal
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition
from pydantic import BaseModel
from langgraph.graph import END, StateGraph, START
#logging.basicConfig(level=logging.DEBUG)
from typing import Callable
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
# Carga todas las variables del archivo .env al entorno
load_dotenv()  
os.environ['USER_AGENT'] = 'Bot_Mecanicos/1.0'
os.environ['GROQ_API_KEY']
os.environ['LANGCHAIN_API_KEY']
os.environ['LANGCHAIN_TRACING_V2']
os.environ['LANGCHAIN_PROJECT']
os.environ['OPENAI_API_KEY']
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

#FILE PATHS
ruta_base_datos = 'database\mecanicos.db'

#LLm Select
llm = ChatOpenAI(model="gpt-4o-mini")
llm1 = ChatGroq(
            model="llama-3.1-70b-versatile",
            temperature=0,
        )

#Prompts
prompt_manger = ChatPromptTemplate.from_messages(
    [
        (
            "system",
           " You are a helpful assistant for a mechanic shop.\n"
           " Your primary role is to assist in creating, reading, updating, and deleting records in the database. Always ensure you have all the necessary data before using a tool, and thoroughly analyze the information required for each operation.\n"
           " When searching for information, be persistent. If your initial search yields no results, expand your search parameters or consider alternative queries before concluding that the data is unavailable. Do not give up after a single unsuccessful attempt.\n"
           " Below is detailed information about the company's operations, including the various tools incorporated and their specific use cases:\n"
            "\n {company_info}\n"
            "By following these guidelines and utilizing the provided tools effectively, you will assist the mechanic shop in maintaining efficient operations, accurate records, and high-quality customer service.\n"
            "If the user greets, or thanks you, respond with a greeting or thank you message. If the user asks for help, provide guidance on how to proceed. If the user requests information, provide the relevant details.\n"
            "Be brief and descriptive in each response.\n"
            "Use very emojis to make the interaction more dynamic and friendly.\n"
            "NEVER RESPOND TO QUESTIONS THAT ARE NOT RELATED TO THE MECHANIC SHOP.\n"
           " \nCurrent time: {time}.",
        ),  
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())


#Utility functions
def format_datetime(dt: Union[datetime, date]) -> str:
    if isinstance(dt, datetime):
        return dt.isoformat() + 'Z'
    elif isinstance(dt, date):
        return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc).isoformat() + 'Z'
    else:
        raise ValueError("Invalid datetime or date object")  

def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print(f"Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)

import logging
from typing import List, Dict, Any, Optional
import mysql.connector

def from_conn_stringx(conn_string: str):
    """
    Parses a MySQL connection string and returns a connection object.

    Args:
        conn_string (str): The connection string in the format 'user:password@host/database'.

    Returns:
        mysql.connector.connection_cext.CMySQLConnection: The MySQL connection object.
    """
    try:
        # Assuming conn_string is in the format 'user:password@host/database'
        pattern = r'^(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^/]+)/(?P<database>.+)$'
        match = re.match(pattern, conn_string)
        if not match:
            raise ValueError("Invalid connection string format.")
        conn_params = match.groupdict()
        
        # Try to establish a connection
        conn = mysql.connector.connect(
            host=conn_params['host'],
            user=conn_params['user'],
            password=conn_params['password'],
            database=conn_params['database'],
            port=3306  # Asegúrate de que este puerto coincida con el de tu servidor
        )
        
        if conn.is_connected():
            print("Conexión exitosa a la base de datos")
        
        return conn

    except mysql.connector.Error as err:
        logging.error(f"Error al conectar con la base de datos MySQL: {err}")
        print(f"Error al conectar con la base de datos MySQL: {err}")
        raise err
    except Exception as e:
        logging.error(f"Error al analizar la cadena de conexión: {e}")
        print(f"Error al analizar la cadena de conexión: {e}")
        raise e

# Define the connection string once

conn_string = 'mecanicos_user:mecanicos_password@db/mecanicos'

# Intentar establecer la conexión
try:
    connection = from_conn_stringx(conn_string)
except Exception as e:
    print(f"Error durante la conexión: {e}")


def create_config(user_phone_number, thread_id=None):
    """Create the config dictionary where duck_id is the user's phone number."""
    config = {
        "configurable": {
            "duck_id": user_phone_number,  # Use the user's phone number as duck_id
            "thread_id": thread_id,
        }
    }
    return config

# Tools
@tool
def add_products_to_order_tool(orden_id: int, product_details: List[Dict[str, int]]) -> None:
    """
    Adds products to an existing service order in the 'mecanicos' database.

    This tool associates multiple products with an existing service order by specifying the order ID and product details. The products are added to the 'Productos_Servicio' table, linking them to a specific service order.

    ### Arguments:
    - `orden_id` (int): ID of the existing service order in the 'Orden_Entrada' table. Must be valid.
    - `product_details` (List[Dict[str, int]]): List of dictionaries with:
        - `'id_producto'` (int): Product ID from the 'Productos' table. Must exist.
        - `'cantidad'` (int): Quantity of the product. Must be greater than zero.

    ### Expected Data Format for `product_details`:
    ```python
    product_details = [
        {"id_producto": 101, "cantidad": 5},
        {"id_producto": 102, "cantidad": 2},
    ]
    ```
    """
    if not orden_id:
        logging.error("El ID de orden no es válido. Por favor, proporcione un ID de orden válido.")
        return {"error": "El ID de orden no es válido."}

    if not product_details:
        logging.error("La lista de productos no puede estar vacía. Por favor, proporcione detalles de los productos.")
        return {"error": "La lista de productos no puede estar vacía."}

    conn = None

    try:
        # Open the database connection using from_conn_stringx
        conn = from_conn_stringx(conn_string)

        cursor = conn.cursor()

        # Verify that the order ID exists in the database
        cursor.execute("SELECT 1 FROM Orden_Entrada WHERE ID_Entrada = %s", (orden_id,))
        if not cursor.fetchone():
            logging.error(f"El ID de orden {orden_id} no existe en la base de datos.")
            cursor.close()
            return {"error": f"El ID de orden {orden_id} no existe en la base de datos."}

        # Call the existing 'add_products_for_order' function to associate products
        messages = add_products_for_order(conn, orden_id, product_details)

        conn.commit()
        logging.info(f"La orden con ID {orden_id} ha sido actualizada exitosamente con los productos asociados.")
        return {"messages": messages}

    except Error as db_error:
        logging.error(f"Ocurrió un error de base de datos: {db_error}")
        return {"error": f"Ocurrió un error de base de datos: {db_error}"}
    except Exception as e:
        logging.error(f"Ocurrió un error inesperado: {e}")
        return {"error": f"Ocurrió un error inesperado: {e}"}
    finally:
        # Ensure the database connection is closed properly
        if conn and conn.is_connected():
            conn.close()


from rabbit_connection import rabbit_url, CONFIG

rabbit_url1 = rabbit_url
#enviar pdf
@tool
def send_product_list_pdf_tool():
    """
    Tool to send the PDF of the product list when requested by the user.

    Returns:
        dict: Status message of the operation
    """
    try:
        # Obtener información del usuario desde la configuración
        config = ensure_config()
        configuration = config.get("configurable", {})
        number = configuration.get("user_id", None)
        
        if not number:
            return {
                'status': 'error',
                'message': 'No client_id (thread_id) provided in the configuration.'
            }

        # Ruta del archivo PDF
        pdf_path = 'src/productos_lista.pdf'

        # Leer el archivo PDF y convertirlo a base64
        with open(pdf_path, 'rb') as file:
            pdf_content = base64.b64encode(file.read()).decode('utf-8')
        
        # Preparar el payload con nombre fijo y contenido en base64
        response_payload = {
            'number': number,
            'response': {
                'filename': 'productos_lista.pdf',  # Nombre fijo del archivo
                'content': pdf_content,  # Contenido en base64
                'content_type': 'application/pdf'
            }
        }
        
        async def send_message():
            # Define rabbit_url
            rabbit_url = rabbit_url1
            consumer = AsyncRabbitMQConsumer(rabbit_url, CONFIG)
            await consumer.connect()
            await consumer.send_response(
                response_payload,
                'Mecanicos-respuesta-Bot'  # Name of the outgoing queue
            )
            # Replace cleanup with connection close
            if consumer.connection:
                await consumer.connection.close()

        # Aplicar nest_asyncio
        nest_asyncio.apply()
        
        # Crear nuevo event loop si no existe
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Ejecutar la función asíncrona
        loop.run_until_complete(send_message())
        
        return {
            'status': 'success',
            'message': 'PDF file sent successfully  and sent to administrator'
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Error sending PDF file: {str(e)}'
        }


#excel
from langchain.tools import tool
import tempfile
import os
import asyncio
import json
from aio_pika import connect_robust, Message, DeliveryMode
import nest_asyncio


@tool
def export_orders_to_excel_tool():
    """
    Tool to create a temporary Excel file with all current records and send it through the outgoing queue.
    
    Returns:
        dict: Status message of the operation
    """
    try:
        # Get user information from the configuration
        config = ensure_config()
        configuration = config.get("configurable", {})
        number = configuration.get("user_id", None)

        if not number:
            return {
                'status': 'error',
                'message': 'No user_id provided in the configuration.'
            }

        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            temp_path = tmp_file.name

        # Export data to the temporary file
        export_orders_to_excel(ruta_base_datos, temp_path)

        # Read the temporary file and convert to base64
        with open(temp_path, 'rb') as file:
            excel_content = base64.b64encode(file.read()).decode('utf-8')

        # Prepare the payload with fixed name and base64 content
        response_payload = {
            'number': number,
            'response': {
                'filename': 'ordenes_entrada.xlsx',
                'content': excel_content,
                'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        }

        async def send_message():
            # Define rabbit_url
            rabbit_url = rabbit_url1
            consumer = AsyncRabbitMQConsumer(rabbit_url, CONFIG)
            await consumer.connect()
            await consumer.send_response(
                response_payload,
                'Mecanicos-respuesta-Bot'  # Name of the outgoing queue
            )
            # Replace cleanup with connection close
            if consumer.connection:
                await consumer.connection.close()

        # Apply nest_asyncio
        import nest_asyncio
        nest_asyncio.apply()

        # Use existing event loop
        loop = asyncio.get_event_loop()
        loop.run_until_complete(send_message())

        # Delete the temporary file
        os.unlink(temp_path)

        return {
            'status': 'success',
            'message': 'Excel file created successfully and sent to administrator.'
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'status': 'error',
            'message': f'Error creating/sending Excel file: {str(e)}'
        }

from mysql.connector import Error


#Camion
@tool
def create_camion_tool(vin: str, numero_unidad: int, kilometraje: int, marca: str, modelo: str) -> Dict[str, Any]:
    """
    Creates a new 'Camion' record in the database.

    Args:
        vin (str): The VIN of the camion.
        numero_unidad (int): The unit number of the camion.
        kilometraje (int): The mileage of the camion.
        marca (str): The brand of the camion.
        modelo (str): The model of the camion.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)

        create_camion(conn, vin, numero_unidad, kilometraje, marca, modelo)
        conn.commit()
        return {"message": f"Camion with VIN '{vin}' created successfully."}

    except Error as e:
        logging.error(f"Database error creating camion: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error creating camion: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()


@tool
def read_camion_tool(vin: str) -> Dict[str, Any]:
    """
    Reads a 'Camion' record from the database.

    Args:
        vin (str): The VIN of the camion to read.

    Returns:
        dict: The camion record or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)

        camion = read_camion(conn, vin)
        if camion:
            return {"camion": camion}
        else:
            return {"message": "Camion not found."}

    except Error as e:
        logging.error(f"Database error reading camion: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error reading camion: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()


@tool
def update_camion_tool(
    vin: str,
    numero_unidad: Optional[int] = None,
    kilometraje: Optional[int] = None,
    marca: Optional[str] = None,
    modelo: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates an existing 'Camion' record in the database.

    Args:
        vin (str): The VIN of the camion to update.
        numero_unidad (int, optional): The new unit number.
        kilometraje (int, optional): The new mileage.
        marca (str, optional): The new brand.
        modelo (str, optional): The new model.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)

        result = update_camion(conn, vin, numero_unidad, kilometraje, marca, modelo)
        conn.commit()
        return result

    except Error as e:
        logging.error(f"Database error updating camion: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error updating camion: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()



@tool
def delete_camion_tool(vin: str) -> Dict[str, Any]:
    """
    Deletes a 'Camion' record from the database.

    Args:
        vin (str): The VIN of the camion to delete.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)

        result = delete_camion(conn, vin)
        conn.commit()
        return result

    except Error as e:
        logging.error(f"Database error deleting camion: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error deleting camion: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

#Orden de entrada############################################################################################################

@tool
def read_orden_entrada_tool(orden_id: int) -> Dict[str, Any]:
    """
    Reads an 'Orden_Entrada' record from the database.

    Args:
        orden_id (int): The ID of the order to read.

    Returns:
        dict: The order record or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        orden = read_orden_entrada(conn, orden_id)
        if orden:
            return {"orden": orden}
        else:
            return {"message": "Orden_Entrada not found."}
    except Error as e:
        logging.error(f"Database error reading Orden_Entrada: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error reading Orden_Entrada: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def update_orden_entrada_tool(
    orden_id: int,
    fecha_entrada: Optional[str] = None,
    status: Optional[str] = None,
    fecha_salida: Optional[str] = None,
    id_camion: Optional[str] = None,
    motivo_entrada: Optional[str] = None,
    motivo_salida: Optional[str] = None,
    tipo: Optional[str] = None,
    kilometraje: Optional[int] = None
) -> Dict[str, Any]:
    """
    Updates an existing 'Orden_Entrada' record in the database.

    Args:
        orden_id (int): The ID of the order to update.
        fecha_entrada (str, optional): New entry date.
        status (str, optional): New status.
        fecha_salida (str, optional): New exit date.
        id_camion (str, optional): New camion VIN.
        tipo (str, optional): New maintenance type.
        motivo_entrada (str, optional): New entry reason.
        motivo_salida (str, optional): New exit reason.
        kilometraje (int, optional): New entry mileage.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        result = update_orden_entrada(
            conn,
            orden_id,
            fecha_entrada=fecha_entrada,
            status=status,
            fecha_salida=fecha_salida,
            id_camion=id_camion,
            motivo_entrada=motivo_entrada,
            motivo_salida=motivo_salida,
            tipo=tipo,
            kilometraje=kilometraje,
        )
        conn.commit()
        return result
    except Error as e:
        logging.error(f"Database error updating Orden_Entrada: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error updating Orden_Entrada: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def delete_orden_entrada_tool(orden_id: int) -> Dict[str, Any]:
    """
    Deletes an 'Orden_Entrada' record from the database.

    Args:
        orden_id (int): The ID of the order to delete.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        result = delete_orden_entrada(conn, orden_id)
        conn.commit()
        return result
    except Error as e:
        logging.error(f"Database error deleting Orden_Entrada: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error deleting Orden_Entrada: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def salida_orden_entrada_tool(
    orden_id: int,
    fecha_salida: str,
    status: str,
    motivo_salida: str,
    kilometraje: int
) -> Dict[str, Any]:
    """
    Updates the exit information of an existing Orden_Entrada.

    Args:
        orden_id (int): ID of the order to update.
        fecha_salida (str): Exit date in 'YYYY-MM-DD' format.
        status (str): New status of the order.
        motivo_salida (str): Reason for the exit.
        kilometraje (int): Current mileage of the vehicle.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        # Generate exit time automatically
        hora_salida = datetime.now().strftime('%H:%M:%S')

        conn = from_conn_stringx(conn_string)
        result = salida_orden_entrada(
            conn=conn,
            orden_id=orden_id,
            fecha_salida=fecha_salida,
            status=status,
            motivo_salida=motivo_salida,
            hora_salida=hora_salida,
            kilometraje=kilometraje
        )
        conn.commit()
        return result
    except Error as e:
        logging.error(f"Database error updating salida for Orden_Entrada: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error updating salida for Orden_Entrada: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()
#Products############|############################################################################################################
@tool
def read_producto_tool(producto_id: int) -> Dict[str, Any]:
    """
    Reads a 'Producto' record from the database.

    Args:
        producto_id (int): The ID of the product to read.

    Returns:
        dict: The product record or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        producto = read_producto(conn, producto_id)
        if producto:
            return {"producto": producto}
        else:
            return {"message": "Producto not found."}
    except Error as e:
        logging.error(f"Database error reading Producto: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error reading Producto: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def update_producto_tool(
    producto_id: int,
    nombre: Optional[str] = None,
    categoria: Optional[str] = None
) -> Dict[str, Any]:
    """
    Updates an existing 'Producto' record in the database.

    Args:
        producto_id (int): The ID of the product to update.
        nombre (str, optional): New product name.
        categoria (str, optional): New product category.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        result = update_producto(conn, producto_id, nombre=nombre, categoria=categoria)
        conn.commit()
        return result
    except Error as e:
        logging.error(f"Database error updating Producto: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error updating Producto: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def delete_producto_tool(producto_id: int) -> Dict[str, Any]:
    """
    Deletes a 'Producto' record from the database.

    Args:
        producto_id (int): The ID of the product to delete.

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        result = delete_producto(conn, producto_id)
        conn.commit()
        return result
    except Error as e:
        logging.error(f"Database error deleting Producto: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error deleting Producto: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def read_productos_servicio_tool(id_orden: int) -> Dict[str, Any]:
    """
    Reads 'Productos_Servicio' records associated with a given order.

    Args:
        id_orden (int): The ID of the order.

    Returns:
        dict: A list of products associated with the order or an error message.
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        productos_servicio = read_productos_servicio(conn, id_orden)
        if productos_servicio:
            return {"productos_servicio": productos_servicio}
        else:
            return {"message": "No products found for the given order."}
    except Error as e:
        logging.error(f"Database error reading Productos_Servicio: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error reading Productos_Servicio: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

from datetime import datetime
import logging
from typing import Dict, Any

# Assuming 'from_conn_stringx' and 'create_orden_entrada' are imported or defined elsewhere.

@tool
def create_order_tool(
    fecha_entrada: str,
    status: str,
    id_camion: str,
    motivo_entrada: str,
    tipo: str,
    lugar: str
) -> Dict[str, Any]:
    """
    Creates a new 'Orden_Entrada' record in the database.

    Args:
        fecha_entrada (str): Entry date in 'YYYY-MM-DD' format.
        status (str): Status of the order ('liberada', 'proceso', 'inactiva').
        id_camion (str): VIN of the truck.
        motivo_entrada (str): Reason for maintenance.
        tipo (str): Maintenance type ('PREVENTIVO', 'CORRECTIVO', 'CONSUMIBLE').
        lugar (str): Location of the maintenance ('PUEBLA', 'VILLA HERMOSA', 'GUADALAJARA').

    Returns:
        dict: A success message or an error message.
    """
    conn = None
    try:
        # Validate input arguments
        if not isinstance(id_camion, str) or not id_camion.strip():
            raise ValueError("The truck VIN is invalid or empty.")
        # Get current timestamp
        hora_registro = datetime.now().strftime('%H:%M')

        # Correct date formatting for 'fecha_entrada'
        try:
            fecha_entrada_obj = datetime.strptime(fecha_entrada, '%Y-%m-%d')
            fecha_entrada = fecha_entrada_obj.strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError("The entry date must be in 'YYYY-MM-DD' format.")

        conn = from_conn_stringx(conn_string)

        # Call the existing 'create_orden_entrada' function
        result = create_orden_entrada(
            conn,
            fecha_entrada,
            status,
            id_camion,
            motivo_entrada,
            tipo,
            hora_registro,
            lugar
        )
        conn.commit()
        return result

    except ValueError as ve:
        logging.error(f"Validation error: {ve}")
        return {"error": str(ve)}
    except Error as e:
        logging.error(f"Database error creating order: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error creating order: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def get_products_used_in_month_tool(year: int, month: int) -> List[Dict[str, Any]]:
    """
    Retrieves all products used and their quantities in all orders for a specified month.

    Args:
        year (int): The year of interest (e.g., 2023).
        month (int): The month of interest (1-12).

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing product name, category, and total quantity used.

    Usage:
        products = get_products_used_in_month_tool(2023, 10)
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        results = get_products_used_in_month(conn, year, month)
        products_list = []
        for product in results:
            products_list.append({
                "Nombre": product[0],
                "Categoria": product[1],
                "TotalCantidad": product[2]
            })
        return products_list
    except Error as e:
        logging.error(f"Database error in get_products_used_in_month_tool: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error in get_products_used_in_month_tool: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()
#########################|############################################################################################################

@tool
def get_product_total_usage_for_truck_tool(
    vin: str,
    product_id: int,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Retrieves the total quantity of a specific product used for a specific truck within a time range.

    Args:
        vin (str): The VIN of the truck.
        product_id (int): The ID of the product.
        start_date (str): The start date in 'YYYY-MM-DD' format.
        end_date (str): The end date in 'YYYY-MM-DD' format.

    Returns:
        Dict[str, Any]: A dictionary containing the total quantity used.

    Usage:
        total_usage = get_product_total_usage_for_truck_tool('1HGCM82633A004352', 1, '2023-01-01', '2023-12-31')
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        total_quantity = get_product_usage_for_truck(conn, vin, product_id, start_date, end_date)
        return {"TotalCantidad": total_quantity}
    except Error as e:
        logging.error(f"Database error in get_product_total_usage_for_truck_tool: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error in get_product_total_usage_for_truck_tool: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def get_products_used_for_truck_tool(vin: str) -> List[Dict[str, Any]]:
    """
    Retrieves all products used and their quantities for a specific truck across all orders.

    Args:
        vin (str): The VIN of the truck.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing product name, category, and total quantity used.

    Usage:
        products = get_products_used_for_truck_tool('1HGCM82633A004352')
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        results = get_products_used_for_truck(conn, vin)
        products_list = []
        for product in results:
            products_list.append({
                "Nombre": product[0],
                "Categoria": product[1],
                "TotalCantidad": product[2]
            })
        return products_list
    except Error as e:
        logging.error(f"Database error in get_products_used_for_truck_tool: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error in get_products_used_for_truck_tool: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def get_order_count_for_branch_tool(branch_name: str) -> Dict[str, Any]:
    """
    Retrieves the number of orders for a specific branch.

    Args:
        branch_name (str): The name or identifier of the branch.

    Returns:
        Dict[str, Any]: A dictionary containing the total number of orders.

    Usage:
        order_count = get_order_count_for_branch_tool('Branch_A')
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        count = get_order_count_for_branch(conn, branch_name)
        return {"TotalOrders": count}
    except Error as e:
        logging.error(f"Database error in get_order_count_for_branch_tool: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error in get_order_count_for_branch_tool: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

@tool
def get_order_details_for_truck_tool(vin: str) -> List[Dict[str, Any]]:
    """
    Retrieves the number of orders, motives, and dates for a specific truck.

    Args:
        vin (str): The VIN of the truck.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing order ID, motive, and date.

    Usage:
        orders = get_order_details_for_truck_tool('1HGCM82633A004352')
    """
    conn = None
    try:
        conn = from_conn_stringx(conn_string)
        order_details = get_order_details_for_truck(conn, vin)
        return order_details
    except Error as e:
        logging.error(f"Database error in get_order_details_for_truck_tool: {e}")
        return {"error": str(e)}
    except Exception as e:
        logging.error(f"Error in get_order_details_for_truck_tool: {e}")
        return {"error": str(e)}
    finally:
        if conn and conn.is_connected():
            conn.close()

#Utility functions
def get_company_info(state) -> str:
    company_info = mechanics_operation
    return {"company_info": company_info}

def delete_messages(state):
    messages = state["messages"]
    if len(messages) > 4 :
        print("Deleting messages")
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:-3]]}


def increment_number_in_string(input_str: str) -> str:
    # Find the first sequence of digits in the string
    match = re.search(r'\d+', input_str)
    
    if match:
        # Extract the number, increment it, and format it back into the string
        number = int(match.group())
        incremented_number = str(number + 1)
        # Replace the original number in the string with the incremented number
        updated_str = input_str[:match.start()] + incremented_number + input_str[match.end():]
        return updated_str
    else:
        # If no number is found, return the original string
        return input_str
    
def get_tool_call_id(messages: list) -> str:
    """
    Checks if the 'messages' variable exists and if 'messages[-2]' has a 'tool_call_id'.

    Args:
        messages (list): A list of message objects or dictionaries.

    Returns:
        str or None: The 'tool_call_id' if it exists, otherwise None.
    """
    try:
        # Access the 'tool_call_id' if it exists in 'messages[-2]'
        tool_call_id =messages[-2].tool_call_id
        return True
    except (IndexError, AttributeError):
        # Return None if 'messages' has fewer than 2 items or 'tool_call_id' doesn't exist
        return None

#Classes
#Graph State and assistant
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    company_info: str

class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}

#Tools assignation
company_tools_safe = [
    read_camion_tool,
    read_orden_entrada_tool,
    read_producto_tool,
    read_productos_servicio_tool,
    add_products_to_order_tool,
    export_orders_to_excel_tool,
    salida_orden_entrada_tool,
    get_products_used_in_month_tool,
    get_product_total_usage_for_truck_tool,
    get_products_used_for_truck_tool,
    send_product_list_pdf_tool,
    get_order_details_for_truck_tool,
]

company_tools_auth = [
    create_camion_tool,
    update_camion_tool,
    delete_camion_tool,
    update_orden_entrada_tool,
    delete_orden_entrada_tool,
    create_order_tool,
    update_producto_tool,
    delete_producto_tool,  
]

tools_auth_names = {t.name for t in company_tools_auth}
# Runnable
runnable =  prompt_manger | llm.bind_tools(company_tools_auth + company_tools_safe)
# Graph
builder = StateGraph(State)
#Node Funcitions
builder.add_node("operation_info", get_company_info)
builder.add_edge(START, "operation_info")
builder.add_node("assistant", Assistant(runnable))
builder.add_node("safe_tools", create_tool_node_with_fallback(company_tools_safe))
builder.add_node("sensitive_tools", create_tool_node_with_fallback(company_tools_auth))
builder.add_edge("operation_info", "assistant")
builder.add_node(delete_messages)
# Define logic
def route_tools(state: State) -> Literal["safe_tools","delete_messages", "sensitive_tools", "__end__"]:
    next_node = tools_condition(state)
    last_message = state["messages"][-1]
    # If no tools are invoked, return to the user
    if next_node == END:
        if not last_message.tool_calls:
            return "delete_messages"
        else:
            return END
    ai_message = state["messages"][-1]
    # This assumes single tool calls. To handle parallel tool calling, you'd want to
    # use an ANY condition
    first_tool_call = ai_message.tool_calls[0]
    if first_tool_call["name"] in tools_auth_names:
        return "sensitive_tools"
    return "safe_tools"

builder.add_conditional_edges("assistant",route_tools)
builder.add_edge("safe_tools", "assistant")
builder.add_edge("sensitive_tools", "assistant")
builder.add_edge("delete_messages", END)

memory = MemorySaver()
part_1_graph = builder.compile(
    checkpointer=memory,
    # NEW: The graph will always halt before executing the "tools" node.
    # The user can approve or reject (or even alter the request) before
    # the assistant continues
    interrupt_before=["sensitive_tools"]
)
########################################33333333333333333
### CONFIGURACION DE RABBITMQ Y CONEXIONES


import os
import asyncio
from rabbit_connection import AsyncRabbitMQConsumer

# Aseguramos cargar las variables de entorno
from dotenv import load_dotenv
load_dotenv()

async def main():
    rabbit_url = "amqp://guest:guest@localhost/"
    config = {
        "configurable": {
            "user_id": None,
            "thread_id": None
        }
    }
    consumer = AsyncRabbitMQConsumer(rabbit_url, config, part_1_graph)
    try:
        await consumer.start_consuming()
    except KeyboardInterrupt:
        print("Deteniendo el consumidor...")
    finally:
        await consumer.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
