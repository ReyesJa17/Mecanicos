import getpass
from langchain_core.messages import AIMessage
import os
import asyncio
import aio_pika
import datetime as dt
from langchain_core.runnables import RunnableLambda, Runnable, RunnableConfig
from datetime import datetime, date, timezone, timedelta
from langgraph.prebuilt import ToolNode
from langsmith import traceable
import logging
from typing import Optional, Union
from datetime import date, datetime
#from langchain import  smith
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated
import uuid
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
import sqlite3
from langchain_core.messages import RemoveMessage
from utilsdb import (
    create_camion,
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
    create_order_with_products,
    mechanics_operation,
    get_products_used_in_month,
    get_product_usage_for_truck,
    get_products_used_for_truck,
    get_order_count_for_branch,
    get_order_details_for_truck,
    export_orders_to_excel,
)

from langchain_core.runnables import ensure_config
from langchain_core.output_parsers import JsonOutputParser,  StrOutputParser
from langchain_core.messages import HumanMessage
from typing import Literal
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition
from pydantic import BaseModel
from langgraph.graph import END, StateGraph, START
import sys
from utilsdb import initialize_database
#logging.basicConfig(level=logging.DEBUG)
from typing import Callable
from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
import openai
load_dotenv()  # Carga todas las variables del archivo .env al entorno

# Ahora puedes acceder a las variables con os.environ
os.environ['GROQ_API_KEY']
os.environ['LANGCHAIN_API_KEY']
os.environ['LANGCHAIN_TRACING_V2']
os.environ['LANGCHAIN_PROJECT']
os.environ['OPENAI_API_KEY']
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

llm = ChatOpenAI(model="gpt-4o-mini")

#FILE PATHS
ruta_base_datos = 'mecanicos.db'
ruta_excel = 'ordenes_entrada.xlsx'

#LLm Select

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
            "If the user greets, or thanks you, respond with a greeting or thank you message. If the user asks for help, provide guidance on how to proceed. If the user requests information, provide the relevant details."
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



def from_conn_stringx(cls, conn_string: str,) -> "SqliteSaver":
    return SqliteSaver(conn=sqlite3.connect(conn_string, check_same_thread=False))


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
    try:
        conn = sqlite3.connect('mecanicos.db')
        create_camion(conn, vin, numero_unidad, kilometraje, marca, modelo)
        conn.close()
        return {"message": f"Camion with VIN '{vin}' created successfully."}
    except Exception as e:
        logging.error(f"Error creating camion: {e}")
        return {"error": str(e)}

@tool
def read_camion_tool(vin: str) -> Dict[str, Any]:
    """
    Reads a 'Camion' record from the database.

    Args:
        vin (str): The VIN of the camion to read.

    Returns:
        dict: The camion record or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        camion = read_camion(conn, vin)
        conn.close()

        if camion:
            return {"camion": camion}
        else:
            return {"message": "Camion not found."}
    except Exception as e:
        logging.error(f"Error reading camion: {e}")
        return {"error": str(e)}

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
        kilometraje (float, optional): The new mileage.
        marca (str, optional): The new brand.
        modelo (str, optional): The new model.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = update_camion(conn, vin, numero_unidad, kilometraje, marca, modelo)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error updating camion: {e}")
        return {"error": str(e)}

@tool
def delete_camion_tool(vin: str) -> Dict[str, Any]:
    """
    Deletes a 'Camion' record from the database.

    Args:
        vin (str): The VIN of the camion to delete.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = delete_camion(conn, vin)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error deleting camion: {e}")
        return {"error": str(e)}


#Orden de entrada

@tool
def read_orden_entrada_tool(orden_id: int) -> Dict[str, Any]:
    """
    Reads an 'Orden_Entrada' record from the database.

    Args:
        orden_id (int): The ID of the order to read.

    Returns:
        dict: The order record or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        orden = read_orden_entrada(conn, orden_id)
        conn.close()

        if orden:
            return {"orden": orden}
        else:
            return {"message": "Orden_Entrada not found."}
    except Exception as e:
        logging.error(f"Error reading Orden_Entrada: {e}")
        return {"error": str(e)}


@tool
def update_orden_entrada_tool(
    orden_id: int,
    id_encargado: Optional[str] = None,
    fecha_entrada: Optional[str] = None,
    status: Optional[str] = None,
    fecha_salida: Optional[str] = None,
    id_camion: Optional[str] = None,
    motivo_entrada: Optional[str] = None,
    motivo_salida: Optional[str] = None,
    tipo: Optional[str] = None,
    kilometraje_entrada: Optional[int] = None
) -> Dict[str, Any]:
    """
    Updates an existing 'Orden_Entrada' record in the database.

    Args:
        orden_id (int): The ID of the order to update.
        id_encargado (str, optional): New encargado ID.
        fecha_entrada (str, optional): New entry date.
        status (str, optional): New status.
        fecha_salida (str, optional): New exit date.
        id_camion (str, optional): New camion VIN.
        tipo (str, optional): New maintenance type.
        motivo_entrada (str, optional): New entry reason.
        motivo_salida (str, optional): New exit reason.
        kilometraje_entrada (float, optional): New entry mileage.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = update_orden_entrada(
            conn,
            orden_id,
            id_encargado=id_encargado,
            fecha_entrada=fecha_entrada,
            status=status,
            fecha_salida=fecha_salida,
            id_camion=id_camion,
            motivo_entrada=motivo_entrada,
            motivo_salida=motivo_salida,
            tipo=tipo,
            kilometraje_entrada=kilometraje_entrada
        )
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error updating Orden_Entrada: {e}")
        return {"error": str(e)}


@tool
def delete_orden_entrada_tool(orden_id: int) -> Dict[str, Any]:
    """
    Deletes an 'Orden_Entrada' record from the database.

    Args:
        orden_id (int): The ID of the order to delete.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = delete_orden_entrada(conn, orden_id)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error deleting Orden_Entrada: {e}")
        return {"error": str(e)}

@tool
def salida_orden_entrada_tool(orden_id: int, fecha_salida: str, status: str,motivo_salida:str) -> Dict[str, Any]:
    """
    Updates the 'fecha_salida' and 'status' of an existing Orden_Entrada.

    Args:
        orden_id (int): ID of the order to update.
        fecha_salida (str): Exit date in 'YYYY-MM-DD' format.
        status (str): New status of the order.
        motivo_salida (str): Reason for the exit.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = salida_orden_entrada(conn, orden_id, fecha_salida, status, motivo_salida)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error updating salida for Orden_Entrada: {e}")
        return {"error": str(e)}


#Products

@tool
def read_producto_tool(producto_id: int) -> Dict[str, Any]:
    """
    Reads a 'Producto' record from the database.

    Args:
        producto_id (int): The ID of the product to read.

    Returns:
        dict: The product record or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        producto = read_producto(conn, producto_id)
        conn.close()

        if producto:
            return {"producto": producto}
        else:
            return {"message": "Producto not found."}
    except Exception as e:
        logging.error(f"Error reading Producto: {e}")
        return {"error": str(e)}

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
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = update_producto(conn, producto_id, nombre=nombre, categoria=categoria)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error updating Producto: {e}")
        return {"error": str(e)}

@tool
def delete_producto_tool(producto_id: int) -> Dict[str, Any]:
    """
    Deletes a 'Producto' record from the database.

    Args:
        producto_id (int): The ID of the product to delete.

    Returns:
        dict: A success message or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        result = delete_producto(conn, producto_id)
        conn.close()
        return result
    except Exception as e:
        logging.error(f"Error deleting Producto: {e}")
        return {"error": str(e)}

#Productos_Servicio

@tool
def read_productos_servicio_tool(id_orden: int) -> Dict[str, Any]:
    """
    Reads 'Productos_Servicio' records associated with a given order.

    Args:
        id_orden (int): The ID of the order.

    Returns:
        dict: A list of products associated with the order or an error message.
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        productos_servicio = read_productos_servicio(conn, id_orden)
        conn.close()

        if productos_servicio:
            return {"productos_servicio": productos_servicio}
        else:
            return {"message": "No products found for the given order."}
    except Exception as e:
        logging.error(f"Error reading Productos_Servicio: {e}")
        return {"error": str(e)}


#Create Orden and associate with camion and products
#Create Orden and associate with camion and products
#Create Orden and associate with camion and products
#Create Orden and associate with camion and products
#Create Orden and associate with camion and products

@tool
def create_order_with_products_tool(
    order_id: int,
    id_encargado: str,
    fecha_entrada: str,
    status: str,
    id_camion: str,
    motivo_entrada: str,
    tipo: str,
    kilometraje_entrada: int
) -> Dict[str, Any]:
    """
    Creates a new 'Orden_Entrada' with associated products by calling the existing 'create_order_with_products' function.

    Args:
        order_id (int): Identifier of the order.
        id_encargado (str): Identifier of the encargado (manager).
        fecha_entrada (str): Entry date in 'YYYY-MM-DD' format.
        status (str): Status of the order.
        id_camion (str): VIN of the truck.
        motivo_entrada (str): Reason for maintenance.
        tipo (str): Maintenance type(PREVENTIVO,CORRECTIVO,CONSUMIBLE).
        kilometraje_entrada (int): Mileage upon entry.

    Returns:
        dict: A success message or an error message.
    """
    try:
        # Send a provisional response indicating that user authorization is required
        provisional_message = "Esperando autorización del usuario para proceder con la creación de la orden."
        send_response(json.dumps({"response": provisional_message}), "Mecanicos-respuesta-Bot")

        # Send an authorization request to the user via RabbitMQ
        prompt = "¿Deseas proceder con la creación de la orden? Responde 'y' para continuar o 'n' para cancelar."
        send_response(json.dumps({"response": prompt}), "Mecanicos-respuesta-Bot")

        # Wait for user authorization (blocking call or implement wait logic)
        user_response = wait_for_user_input(order_id)

        if user_response.strip().lower() != 'y':
            cancel_message = "La operación fue cancelada por el usuario."
            send_response(json.dumps({"response": cancel_message}), "Mecanicos-respuesta-Bot")
            return {"messages": [{"content": cancel_message, "tool_call_id": "call_f0xd8HGKt17IEIKNGqqzGtIC"}]}

        # Open the database connection
        conn = sqlite3.connect('mecanicos.db')

        # Call the existing 'create_order_with_products' function
        result = create_order_with_products(
            conn,
            order_id,
            id_encargado,
            fecha_entrada,
            status,
            id_camion,
            motivo_entrada,
            tipo,
            kilometraje_entrada
        )

        # Close the database connection
        conn.close()

        # Extract response messages
        response_messages = result.get("messages", [])
        if not response_messages:
            response_messages = ["Operación completada sin mensajes adicionales."]

        # Send the generated messages to the user via RabbitMQ if there are messages
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            channel = connection.channel()
            for message in response_messages:
                if message:  # Ensure message is not empty
                    response_payload = json.dumps({"response": message})
                    send_response(response_payload, "Mecanicos-respuesta-Bot")
            connection.close()
        except Exception as rabbitmq_error:
            logging.error(f"Error sending response to RabbitMQ: {rabbitmq_error}")

        return {"messages": [{"content": "Orden creada exitosamente.", "tool_call_id": "call_f0xd8HGKt17IEIKNGqqzGtIC"}]}

    except Exception as e:
        logging.error(f"Error creating order with products: {e}")
        error_message = {"error": f"Error al procesar la solicitud: {str(e)}"}

        # Send the error message through the function send_response
        try:
            error_payload = json.dumps(error_message)
            send_response(error_payload, "Mecanicos-respuesta-Bot")
        except Exception as rabbitmq_error:
            logging.error(f"Error sending error response to RabbitMQ: {rabbitmq_error}")

        return {"messages": [{"content": str(error_message), "tool_call_id": "call_f0xd8HGKt17IEIKNGqqzGtIC"}]}

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
    try:
        conn = sqlite3.connect('mecanicos.db')
        results = get_products_used_in_month(conn, year, month)
        conn.close()

        products_list = []
        for product in results:
            products_list.append({
                "Nombre": product[0],
                "Categoria": product[1],
                "TotalCantidad": product[2]
            })
        return products_list
    except Exception as e:
        logging.error(f"Error in get_products_used_in_month_tool: {e}")
        return {"error": str(e)}


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
        total_usage = get_product_usage_for_truck_tool('1HGCM82633A004352', 1, '2023-01-01', '2023-12-31')
    """
    try:
        conn = sqlite3.connect('mecanicos.db')
        total_quantity = get_product_usage_for_truck(conn, vin, product_id, start_date, end_date)
        conn.close()

        return {"TotalCantidad": total_quantity}
    except Exception as e:
        logging.error(f"Error in get_product_usage_for_truck_tool: {e}")
        return {"error": str(e)}


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
    try:
        conn = sqlite3.connect('mecanicos.db')
        results = get_products_used_for_truck(conn, vin)
        conn.close()

        products_list = []
        for product in results:
            products_list.append({
                "Nombre": product[0],
                "Categoria": product[1],
                "TotalCantidad": product[2]
            })
        return products_list
    except Exception as e:
        logging.error(f"Error in get_products_used_for_truck_tool: {e}")
        return {"error": str(e)}


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
    try:
        conn = sqlite3.connect('mecanicos.db')
        count = get_order_count_for_branch(conn, branch_name)
        conn.close()

        return {"TotalOrders": count}
    except Exception as e:
        logging.error(f"Error in get_order_count_for_branch_tool: {e}")
        return {"error": str(e)}


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
    try:
        conn = sqlite3.connect('mecanicos.db')
        order_details = get_order_details_for_truck(conn, vin)
        conn.close()

        return order_details
    except Exception as e:
        logging.error(f"Error in get_order_details_for_truck_tool: {e}")
        return {"error": str(e)}



#Utility functions
def get_company_info(state) -> str:
    company_info = mechanics_operation
    return {"company_info": company_info}

def delete_messages(state):
    messages = state["messages"]
    if len(messages) > 3:
        print("Deleting messages")
        return {"messages": [RemoveMessage(id=m.id) for m in messages[:-3]]}


#Classes

#Graph State

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
    create_order_with_products_tool,
    salida_orden_entrada_tool,
    get_products_used_in_month_tool,
    get_product_total_usage_for_truck_tool,
    get_products_used_for_truck_tool,
    get_order_details_for_truck_tool,
]

company_tools_auth = [
    create_camion_tool,
    update_camion_tool,
    delete_camion_tool,
    update_orden_entrada_tool,
    delete_orden_entrada_tool,
 
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
builder.add_node(
    "sensitive_tools", create_tool_node_with_fallback(company_tools_auth)
)

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


builder.add_conditional_edges(
    "assistant",
    route_tools,
)
builder.add_edge("safe_tools", "assistant")
builder.add_edge("sensitive_tools", "assistant")
builder.add_edge("delete_messages", END)


memory = MemorySaver()
part_1_graph = builder.compile(
    checkpointer=memory,
    # NEW: The graph will always halt before executing the "tools" node.
    # The user can approve or reject (or even alter the request) before
    # the assistant continues
    interrupt_before=["sensitive_tools"],
)
#Run Test

tutorial_questions = [
    "hi",
    "Is the doctor free for an appointment on may 30 at 9 am?",
    "Great! Can you book that appointment for me?",
    "Thanks",
]



"""thread_id = str(uuid.uuid4())


configuration = {
    "configurable": {
        # The passenger_id is used in our flight tools to
        # fetch the user's flight information
        "duck_id": "1",
        # Checkpoints are accessed by thread_id
        "thread_id": thread_id,
    }
}



"""

###PRINCIPAL






def wait_for_user_input(user_id, timeout=60):
    """
    Espera la respuesta del usuario con manejo mejorado del timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        for message in list(captured_messages):
            if message.get("number") == user_id:
                captured_messages.remove(message)
                return message.get("textMessage")
        time.sleep(0.5)
    return None






async def get_response(question, user_id):
    """
    Maneja la respuesta del grafo, autorizando herramientas sensibles si es necesario.
    
    Args:
        question (str): Pregunta o mensaje del usuario
        user_id (str/int): Identificador único del usuario
        
    Returns:
        str: Respuesta final del grafo
    """
    config = {"configurable": {"thread_id": str(user_id)}}
    current_messages = []

    try:
        # Inicializar el stream con la configuración
        stream = part_1_graph.stream({"messages": [("user", question)]}, config, stream_mode="values")
        
        # Recolectar mensajes iniciales
        async for event in stream:
            current_messages.append(event)

        # Obtener estado inicial
        snapshot = await part_1_graph.get_state(config)

        while snapshot.next:
            if current_messages:
                last_message = current_messages[-1]
                tool_calls = (last_message.kwargs.get("tool_calls", []) 
                            if hasattr(last_message, "kwargs") 
                            else [])

                if tool_calls:
                    tool_call = tool_calls[0]
                    tool_name = (tool_call.get("name", "herramienta desconocida") 
                               if isinstance(tool_call, dict) 
                               else getattr(tool_call, "name", "herramienta desconocida"))

                    # Enviar solicitud de autorización
                    auth_message = (f"Se requiere autorización para la herramienta: {tool_name}. "
                                  "Responde con 'y' para aprobar o cualquier otra cosa para denegar.")
                    await send_response({
                        "number": user_id, 
                        "response": auth_message
                    }, queue_name=f"Mecanicos-respuesta-Bot")

                    # Esperar respuesta del usuario
                    user_response = await wait_for_user_input(user_id)
                    if user_response is None:
                        timeout_msg = "Timeout de autorización. Herramienta no aprobada."
                        await send_response({
                            "number": user_id, 
                            "response": timeout_msg
                        }, queue_name=f"Mecanicos-respuesta-Bot")
                        return timeout_msg

                    if user_response.lower() == 'y':
                        await send_response({
                            "number": user_id, 
                            "response": "Herramienta aprobada. Continuando..."
                        }, queue_name=f"Mecanicos-respuesta-Bot")
                        
                        await part_1_graph.aupdate_state(
                            config, 
                            values={"messages": current_messages}, 
                            as_node="sensitive_tools"
                        )
                    else:
                        await send_response({
                            "number": user_id, 
                            "response": "Herramienta denegada. Cancelando la operación."
                        }, queue_name=f"Mecanicos-respuesta-Bot")
                        
                        tool_call_id = (tool_call.get("id") 
                                      if isinstance(tool_call, dict) 
                                      else getattr(tool_call, "id", None))
                        
                        if tool_call_id:
                            denial_message = {
                                "tool_call_id": tool_call_id, 
                                "content": f"API call denied by user. Reasoning: '{user_response}'. "
                                         "Continue assisting, accounting for the user's input."
                            }
                            await part_1_graph.aupdate_state(
                                config, 
                                values={"messages": [denial_message]}, 
                                as_node="assistant"
                            )
            else:
                print("No hay mensajes disponibles para procesar en el snapshot actual.")

            snapshot = await part_1_graph.get_state(config)

    except AttributeError as e:
        error_message = f"Error de atributos: {str(e)}. Verifica que el objeto tenga los métodos correctos."
        await send_response({
            "number": user_id, 
            "response": error_message
        }, queue_name=f"Mecanicos-respuesta-Bot")
        return error_message
        
    except TypeError as e:
        error_message = f"Error de tipos: {str(e)}. Verifica que los tipos de datos sean correctos."
        await send_response({
            "number": user_id, 
            "response": error_message
        }, queue_name=f"Mecanicos-respuesta-Bot")
        return error_message
        
    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
        await send_response({
            "number": user_id, 
            "response": error_message
        }, queue_name=f"Mecanicos-respuesta-Bot")
        return error_message

    # Procesar respuesta final
    if current_messages:
        last_event = current_messages[-1]
        response_content = (last_event.kwargs.get("content", "No hay respuesta disponible") 
                          if hasattr(last_event, "kwargs") 
                          else getattr(last_event, "content", "No hay respuesta disponible"))
        
        await send_response({
            "number": user_id, 
            "response": response_content
        }, queue_name=f"Mecanicos-respuesta-Bot")
        return response_content

    await send_response({
        "number": user_id, 
        "response": "No hay respuesta disponible"
    }, queue_name=f"Mecanicos-respuesta-Bot")
    return "No hay respuesta disponible"





# Transcribir el archivo de audio utilizando la API de Groq

import requests
def transcribe_audio_groq(wav_file_path):
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    try:
        with open(wav_file_path, 'rb') as audio_file:
            files = {
                'file': audio_file
            }
            data = {
                'model': 'whisper-large-v3-turbo',
                'response_format': 'json',
                'temperature': 0.0
            }
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()  # Lanza un error si la respuesta tiene un estatus de error
            response_data = response.json()
            transcribed_text = response_data.get("text", "")

            if transcribed_text:
                # Paso adicional: Enviar la transcripción al LLM para una mejor respuesta
                
                qa_prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a specialized transcription improvement assistant. Your sole function is to enhance the clarity and comprehensibility of the input transcription. Follow these strict guidelines:

                    1. Provide ONLY the improved version of the input transcription.
                    2. Do not add any commentary, explanations, or additional information.
                    3. Maintain the original meaning and intent of the transcription.
                    4. Replace local jargon or complex terminology with more widely understood equivalents.
                    5. Correct any grammatical errors or awkward phrasings to improve readability.
                    6. Ensure the improved transcription flows naturally and is easily understood by a general audience.
                    7. If the input is already clear and standard, return it unchanged.
                    8. Do not include any introductory or concluding remarks in your response.

                    Your output should consist solely of the improved transcription text."""),
                        ("human", transcribed_text),
                        ])


                prompt = qa_prompt.format()

                # Generar la respuesta utilizando el modelo Groq
                response = llm.invoke([{"role": "user", "content": prompt}])  # Cambié a invoke para llamar al modelo
                return response.content
            else:
                return "No se pudo transcribir el audio."
    except requests.exceptions.RequestException as e:
        return f"Error al realizar la solicitud: {e}"



# Procesar mensajes de chat
import json
import base64
import os
import time
import subprocess
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

# Lista global para capturar mensajesimport json
import pika

captured_messages = []

def send_response(response, queue_name):
    """Función para enviar respuestas a RabbitMQ"""
    try:
        # Crear una nueva conexión para cada envío
        credentials = pika.PlainCredentials('guest', 'guest')
        connection_params = pika.ConnectionParameters(
            host='localhost',
            port=5672,
            virtual_host='/',
            credentials=credentials,
            heartbeat=600
        )
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        # Declarar la cola con los argumentos correctos
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            arguments={
                'x-message-ttl': 60000,
                'x-max-length': 1000  # Added missing argument
            }
        )

        # Verificar y serializar la respuesta
        if isinstance(response, dict):
            response_str = json.dumps(response)  # Serializar a JSON
        elif isinstance(response, str):
            response_str = response
        else:
            raise ValueError("El formato de la respuesta no es compatible. Debe ser un dict o una str.")

        # Publicar el mensaje
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=response_str,
            properties=pika.BasicProperties(
                delivery_mode=2,  # mensaje persistente
                content_type='application/json'
            )
        )
        print(f"[x] Respuesta enviada a {queue_name}: {response_str}")

    except Exception as e:
        print(f"Error al enviar respuesta: {e}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

class RabbitMQConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.queue_args = {
            'x-message-ttl': 60000,  # TTL de 60 segundos
            'x-max-length': 1000,    # Maximum queue length
            'durable': True
        }
        self.queues = ['Mecanicos-chat', 'Mecanicos-audio']
        self.temp_files = {
            'ogg': "/tmp/temp_audio.ogg",
            'wav': "/tmp/temp_audio.wav"
        }

    def connect(self):
        """Establece la conexión con RabbitMQ con reintentos"""
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                credentials = pika.PlainCredentials('guest', 'guest')
                parameters = pika.ConnectionParameters(
                    host='localhost',
                    port=5672,
                    virtual_host='/',
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                print("[*] Conexión establecida con RabbitMQ")
                return True
            except AMQPConnectionError as e:
                retry_count += 1
                wait_time = min(pow(2, retry_count), 30)
                print(f"Intento {retry_count}/{max_retries} fallido. Reintentando en {wait_time} segundos...")
                time.sleep(wait_time)
        
        print("No se pudo establecer conexión después de varios intentos")
        return False

    def setup_queues(self):
        """Configura las colas con los argumentos correctos"""
        try:
            for queue in self.queues:
                self.channel.queue_declare(
                    queue=queue,
                    durable=True,
                    arguments={
                        'x-message-ttl': 60000,
                        'x-max-length': 1000  # Added missing argument
                    }
                )
            
            # Declarar la cola de respuesta del bot
            self.channel.queue_declare(
                queue='Mecanicos-respuesta-Bot',
                durable=True,
                arguments={
                    'x-message-ttl': 60000,
                    'x-max-length': 1000  # Added missing argument
                }
            )
        except Exception as e:
            print(f"Error al configurar las colas: {e}")
            raise

    def process_audio_message(self, message):
        """Procesa mensajes de audio"""
        try:
            audio_base64 = message.get("audio")
            if not audio_base64 or not audio_base64.strip():
                print("Advertencia: Audio vacío o inválido")
                return None

            # Decodificar el audio
            audio_data = base64.b64decode(audio_base64)
            with open(self.temp_files['ogg'], "wb") as audio_file:
                audio_file.write(audio_data)

            # Convertir OGG a WAV
            subprocess.run(
                ["ffmpeg", "-y", "-i", self.temp_files['ogg'], self.temp_files['wav']], 
                check=True
            )

            # Transcribir el audio
            return transcribe_audio_groq(self.temp_files['wav'])

        except Exception as e:
            print(f"Error procesando audio: {e}")
            return None
        finally:
            self.cleanup_temp_files()

    def cleanup_temp_files(self):
        """Limpia los archivos temporales"""
        for file_path in self.temp_files.values():
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"Error al eliminar archivo temporal {file_path}: {e}")

    def handle_user_message(self, message, user_id):
        """Procesa los mensajes del usuario y los agrega a captured_messages"""
        if "textMessage" in message:
            # Agregar el mensaje a la lista de mensajes capturados
            captured_messages.append(message)
            print(f"[x] Mensaje capturado para usuario {user_id}: {message}")

    def process_message(self, ch, method, properties, body):
        """Callback principal para procesar mensajes"""
        try:
            message = json.loads(body.decode())
            print(f"[x] Mensaje recibido en {method.routing_key}: {message}")
            
            user_id = message.get("number")
            if not user_id:
                raise ValueError("Campo 'number' faltante o inválido")

            # Manejar el mensaje del usuario
            self.handle_user_message(message, user_id)

            config_chat = {"configurable": {"thread_id": user_id}}
            
            if method.routing_key == "Mecanicos-chat":
                user_message = message.get("textMessage")
                if not user_message:
                    raise ValueError("Campo 'textMessage' faltante o inválido")
                get_response(user_message, config_chat)
                
            elif method.routing_key == "Mecanicos-audio":
                transcribed_text = self.process_audio_message(message)
                if transcribed_text:
                    get_response(transcribed_text, config_chat)

        except json.JSONDecodeError:
            print("Error: Mensaje recibido no es JSON válido")
        except Exception as e:
            print(f"Error procesando mensaje: {e}")
            if user_id:
                error_message = f"Error al procesar el mensaje: {str(e)}"
                send_response(
                    json.dumps({"number": user_id, "response": error_message}),
                    'Mecanicos-respuesta-Bot'
                )

    def start_consuming(self):
        """Inicia el consumo de mensajes con manejo de errores"""
        while True:
            try:
                if not self.connection or self.connection.is_closed:
                    if not self.connect():
                        continue

                self.setup_queues()
                
                for queue in self.queues:
                    self.channel.basic_consume(
                        queue=queue,
                        on_message_callback=self.process_message,
                        auto_ack=True
                    )

                print("[*] Esperando mensajes. Presiona CTRL+C para salir")
                self.channel.start_consuming()

            except (AMQPConnectionError, AMQPChannelError) as e:
                print(f"Error de conexión: {e}. Reintentando...")
                time.sleep(5)
            except KeyboardInterrupt:
                print("Deteniendo el consumidor...")
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                break
            except Exception as e:
                print(f"Error inesperado: {e}")
                if self.connection and not self.connection.is_closed:
                    self.connection.close()
                time.sleep(5)



async def process_questions(rabbit_url, queue_name, config):
    # Connect to RabbitMQ
    connection = await aio_pika.connect_robust(rabbit_url)
    channel = await connection.channel()

    # Declare queues
    question_queue = await channel.declare_queue(queue_name, durable=True)
    approval_queue = await channel.declare_queue(f"{queue_name}_approval", durable=True)

    async with connection:
        async for question_message in question_queue:
            question = question_message.body.decode()
            print(f"Received question: {question}")

            # Stream events based on received question
            events = part_1_graph.stream({"messages": ("user", question)}, config, stream_mode="values")
            for event in events:
                _print_event(event, _printed=True)
            
            snapshot = part_1_graph.get_state(config)

            # Check if there's a tool call that needs user approval
            while snapshot.next:
                # Ask the user for approval through RabbitMQ
                approval_request = "Do you approve of the above actions? Type 'y' to continue; otherwise, explain your requested change."
                await channel.default_exchange.publish(
                    aio_pika.Message(body=approval_request.encode()),
                    routing_key=f"{queue_name}_approval"
                )

                # Wait for user input from approval queue
                async for approval_message in approval_queue:
                    user_input = approval_message.body.decode()
                    approval_message.ack()  # Acknowledge that approval input was received

                    if user_input.strip().lower() == "y":
                        # Proceed with the action
                        result = await part_1_graph.invoke(None, config)
                    else:
                        # Deny tool call and provide reasoning
                        result = await part_1_graph.invoke(
                            {
                                "messages": [
                                    ToolMessage(
                                        tool_call_id=event["messages"][-1].tool_calls[0]["id"],
                                        content=f"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input.",
                                    )
                                ]
                            },
                            config,
                        )
                    
                    snapshot = part_1_graph.get_state(config)
                    if not snapshot.next:
                        break  # Break if no further interrupts are required

            # Send the last message content back through RabbitMQ
            final_message = result.get("messages")[-1].content
            await channel.default_exchange.publish(
                aio_pika.Message(body=final_message.encode()),
                routing_key=f"{queue_name}_response"
            )

            question_message.ack()  # Acknowledge that the question has been processed


# Example usage:
# asyncio.run(process_questions("amqp://guest:guest@localhost/", "questions_queue", config))

def main():
    consumer = RabbitMQConsumer()
    consumer.start_consuming()

if __name__ == "__main__":
    captured_messages = []
    main()
