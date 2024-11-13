# rabbit_connection.py

import os
import json
import base64
import time
import subprocess
import asyncio
import aio_pika
from aio_pika import connect_robust, Message, DeliveryMode
from aio_pika.exceptions import QueueEmpty
from pika.exceptions import AMQPConnectionError, AMQPChannelError
from langchain_core.messages.tool import ToolMessage

# Aseguramos cargar las variables de entorno
from dotenv import load_dotenv
load_dotenv()

# Obtener variables de entorno
RABBIT_USER = os.getenv('RABBIT_USER', 'guest')
RABBIT_PASSWORD = os.getenv('RABBIT_PASSWORD', 'guest')
RABBIT_HOST = os.getenv('RABBITMQ_HOST', 'localhost')

rabbit_url = f"amqp://{RABBIT_USER}:{RABBIT_PASSWORD}@{RABBIT_HOST}/"

CONFIG = {
    'queues': {
        'incoming_chat': 'Mecanicos-chat',
        'incoming_audio': 'Mecanicos-audio',
        'approval': 'Mecanicos-approval',
        'outgoing': 'Mecanicos-respuesta-Bot'
    },
    'rabbit': {
        'user': RABBIT_USER,
        'password': RABBIT_PASSWORD,
        'host': RABBIT_HOST,
        'reconnect_delay': 5000,
        'max_retries': 5
    },
    'app': {
        'id': 'Mecanicos',
        'queue_config': {
            'durable': True,
            'arguments': {
                'x-message-ttl': 60000,
                'x-max-length': 1000
            }
        }
    }
}
import re
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

import requests
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

os.environ['OPENAI_API_KEY']
llm = ChatOpenAI(model="gpt-4o-mini")
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

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


captured_messages = []
class AsyncRabbitMQConsumer:

    def __init__(self, rabbit_url, config, part_1_graph=None):
        self.rabbit_url = rabbit_url
        self.config = config
        self.part_1_graph = part_1_graph
        self.connection = None
        self.channel = None
        self.temp_files = {
            'ogg': "/tmp/temp_audio.ogg",
            'wav': "/tmp/temp_audio.wav"
        }
        self.queue_args = {
            'x-message-ttl': 60000,
            'x-max-length': 1000
        }
        self.printed_messages = set()
        self.captured_messages = []

        self.approval_states = {}  # Diccionario para mantener estados de aprobación por usuario


        # Inicializar 'configurable' si no existe
        if "configurable" not in self.config:
            self.config["configurable"] = {}

    import os
    from aio_pika import connect_robust

    async def connect(self):
        """Establece la conexión con RabbitMQ"""
        rabbit_user = os.getenv('RABBIT_USER', 'guest')
        rabbit_password = os.getenv('RABBIT_PASSWORD', 'guest')
        rabbit_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        rabbit_url = f'amqp://{rabbit_user}:{rabbit_password}@{rabbit_host}:5672/'

        try:
            self.connection = await connect_robust(
                rabbit_url,
                timeout=300,
                heartbeat=600
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)
            return True
        except Exception as e:
            print(f"Error de conexión: {e}")
            return False

        
    async def setup_queues(self):
        """Configura las colas necesarias"""
        try:
            # Declarar las colas utilizando la configuración especificada en CONFIG
            for queue_key in ['incoming_chat', 'incoming_audio',  'outgoing']:
                queue_name = CONFIG['queues'][queue_key]
                await self.channel.declare_queue(
                    queue_name,
                    durable=CONFIG['app']['queue_config']['durable'],
                    arguments=CONFIG['app']['queue_config']['arguments']
                )
            return True
        except Exception as e:
            print(f"Error al configurar las colas: {e}")
            return False

    async def send_response(self, response, queue_name):
        """
        Envía respuestas a RabbitMQ de forma asíncrona
        
        Args:
            response: Respuesta a enviar (dict o str)
            queue_name: Nombre de la cola de destino
        """
        try:
            # Verificar la conexión de manera correcta
            if self.connection is None or self.connection.is_closed:
                await self.connect()

            # Verificar y serializar la respuesta
            if isinstance(response, dict):
                response_str = json.dumps(response)
            elif isinstance(response, str):
                response_str = response
            else:
                raise ValueError("El formato de la respuesta no es compatible. Debe ser un dict o una str.")

            # Asegurarse de que tenemos un canal válido
            if self.channel is None or self.channel.is_closed:
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)

            # Declarar la cola de forma asíncrona
            await self.channel.declare_queue(
                queue_name,
                durable=True,
                arguments=self.queue_args
            )

            # Crear y enviar el mensaje
            message = Message(
                body=response_str.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type='application/json'
            )

            await self.channel.default_exchange.publish(
                message,
                routing_key=queue_name
            )

            print(f"[x] Respuesta enviada a {queue_name}: {response_str}")
            self.captured_messages.append(response_str)

        except Exception as e:
            print(f"Error al enviar respuesta asíncrona: {e}")
            import traceback
            print(traceback.format_exc())

#####PROCESAR MENSAJES CON EL GRAFO
    async def process_message(self, message,part_1_graph, queue_name):
        """Procesa los mensajes recibidos"""
        async with message.process():
            try:
                print(f"Procesando mensaje de la cola: {queue_name}")
                message_data = json.loads(message.body.decode())
                user_id = message_data.get("number")
                
                if not user_id:
                    raise ValueError("Campo 'number' faltante o inválido")

                if "configurable" not in self.config:
                    self.config["configurable"] = {}
                
                self.config["configurable"]["user_id"] = user_id
                if self.config["configurable"].get("thread_id") is None:
                    self.config["configurable"]["thread_id"] = "1"

                final_message = None
                last_event = None  # Almacenar el último evento
    

                if queue_name == CONFIG['queues']['incoming_chat']:
                    print("Entró en el procesamiento de chat")
                    user_message = message_data.get("textMessage")

                    if not user_message:
                        raise ValueError("Campo 'textMessage' faltante o inválido")
                    
                    if user_message.lower() == "exit":
                        self.config["configurable"]["thread_id"] = increment_number_in_string(self.config["configurable"]["thread_id"])
                    
                    stream_input = {"messages": [("user", user_message)]}
                    config = self.config
            
                    try:
                        preview = part_1_graph.get_state(config)
                        if not preview.next:
                            
                            events = part_1_graph.stream(
                                stream_input, 
                                config, 
                                stream_mode="values"
                            )

                            # Procesar todos los eventos
                            for event in events:
                                last_event = event  # Guardar el último evento
                                messages = event.get("messages", [])
                                if messages:
                                    last_message = messages[-1]
                                    final_message = last_message.content
                            
                            
                            if get_tool_call_id(messages) is True:
                                print("Se ejecutó una herramienta no sensible")
                                self.config["configurable"]["thread_id"] = increment_number_in_string(self.config["configurable"]["thread_id"])

                        # Después de procesar los eventos, verificar si el grafo se detuvo esperando aprobación
                        snapshot = part_1_graph.get_state(config)
                        if snapshot.next and not user_message.lower() in ['y', 'n']:  # Solo pedir aprobación si no es respuesta y/n
                            i = 0
                            print(user_message)
                            
                            i += 1
                            
                            if i < 2:
                                approval_request = "Se requiere tu aprobación para continuar. Escribe 'y' para aprobar o 'n' para denegar la solicitud."
                                approval_payload = {
                                    "number": user_id,
                                    "response": approval_request
                                }
                                await self.send_response(
                                    approval_payload,
                                    CONFIG['queues']['outgoing']
                                )
                                print(f"Solicitud de aprobación enviada: {approval_payload}")
                        
                        elif snapshot.next and user_message.lower() == 'y':
                            print("Se ejecutó la herramienta")
                            result = part_1_graph.invoke(None, config)
                            messages = result.get("messages", [])
                            self.config["configurable"]["thread_id"] = increment_number_in_string(self.config["configurable"]["thread_id"])
                            if messages:
                                last_message = messages[-1]
                                final_message = last_message.content
                        
                        elif snapshot.next and user_message.lower() == 'n':
                            print("Se denegó la acción")
                           
                            metadata = snapshot.metadata
                            ai_message = metadata['writes']['assistant']['messages']
                            tool_calls = ai_message.additional_kwargs['tool_calls']
                            last_tool_id = tool_calls[-1]['id'] if tool_calls else None
                            print(f"Último ID de herramienta: {last_tool_id}")
                            

                            if last_tool_id:
                                result = part_1_graph.invoke(
                                    {
                                        "messages": [
                                            ToolMessage(
                                                tool_call_id=last_tool_id,
                                                content=f"La llamada a la API fue denegada por el usuario. Razonamiento: 'Cambio de parecer'. Continúa asistiendo considerando la entrada del usuario.",
                                            )
                                        ]
                                    },
                                    config,
                                )
                                messages = result.get("messages", [])
                                if messages:
                                    last_message = messages[-1]
                                    final_message = last_message.content
                            else:
                                final_message = "La acción ha sido denegada. ¿En qué más puedo ayudarte?"

                    except Exception as e:
                        print(f"Error en stream de eventos: {e}")
                        import traceback
                        print(traceback.format_exc())

                elif queue_name == CONFIG['queues']['incoming_audio']:
                    # Aquí iría la lógica para procesar mensajes de audio###################################################
                    print("Entró en el procesamiento de audio")
                # Procesar el mensaje de audio y convertirlo a texto
                    transcribed_text = self.process_audio_message(message_data)
                    if not transcribed_text:
                        raise ValueError("No se pudo procesar el mensaje de audio")
                    
                    print(f"Texto transcrito: {transcribed_text}")
                    
                    # Usar el texto transcrito como entrada para el grafo
                    stream_input = {"messages": [("user", transcribed_text)]}
                    config = self.config
                    
                    try:
                        preview = part_1_graph.get_state(config)
                        if not preview.next:
                            events = part_1_graph.stream(
                                stream_input, 
                                config, 
                                stream_mode="values"
                            )

                            # Procesar todos los eventos
                            for event in events:
                                last_event = event
                                messages = event.get("messages", [])
                                if messages:
                                    last_message = messages[-1]
                                    final_message = last_message.content

                        # Manejar la aprobación para mensajes de audio
                        snapshot = part_1_graph.get_state(config)
                        
                        if snapshot.next and not transcribed_text.lower() in ['y', 'n']:  # Solo pedir aprobación si no es respuesta y/n
                            i = 0
                            print(transcribed_text)
                            
                            i += 1
                            
                            if i < 2:
                                approval_request = "Se requiere tu aprobación para continuar. Escribe 'y' para aprobar o 'n' para denegar la solicitud."
                                approval_payload = {
                                    "number": user_id,
                                    "response": approval_request
                                }
                                await self.send_response(
                                    approval_payload,
                                    CONFIG['queues']['outgoing']
                                )
                                print(f"Solicitud de aprobación enviada: {approval_payload}")
                        
                        elif snapshot.next and transcribed_text.lower() == 'y':
                            print("Se ejecutó la herramienta")
                            result = part_1_graph.invoke(None, config)
                            messages = result.get("messages", [])
                            if messages:
                                last_message = messages[-1]
                                final_message = last_message.content
                        
                        elif snapshot.next and transcribed_text.lower() == 'n':
                            print("Se denegó la acción")

                            if last_event and "messages" in last_event:
                                result = await part_1_graph.invoke(
                                    {
                                        "messages": [
                                            ToolMessage(
                                                tool_call_id=last_event["messages"][-1].tool_calls[0]["id"],
                                                content=f"La llamada a la API fue denegada por el usuario. Razonamiento: '{transcribed_text}'. Continúa asistiendo considerando la entrada del usuario.",
                                            )
                                        ]
                                    },
                                    config,
                                )
                                messages = result.get("messages", [])
                                if messages:
                                    last_message = messages[-1]
                                    final_message = last_message.content
                            else:
                                final_message = "La acción ha sido denegada. ¿En qué más puedo ayudarte?"

                    except Exception as e:
                        print(f"Error en stream de eventos: {e}")
                        import traceback
                        print(traceback.format_exc())
                    pass
                else:
                    raise ValueError(f"Mensaje recibido de una cola desconocida: {queue_name}")

                # Enviar respuesta de forma asíncrona
                if final_message:
                    response_payload = {
                        "number": user_id,
                        "response": final_message
                    }
                    
                    await self.send_response(
                        response_payload,
                        CONFIG['queues']['outgoing']
                    )
                    print(f"Respuesta enviada: {response_payload}")

            except Exception as e:
                print(f"Error procesando mensaje: {e}")
                import traceback
                print(traceback.format_exc())

    def process_audio_message(self, message_data):
        """Procesa mensajes de audio"""
        try:
            audio_base64 = message_data.get("audio")
            if not audio_base64:
                return None

            # Decodificar y guardar el audio
            audio_data = base64.b64decode(audio_base64)
            with open(self.temp_files['ogg'], "wb") as audio_file:
                audio_file.write(audio_data)

            # Convertir OGG a WAV
            subprocess.run(
                ["ffmpeg", "-y", "-i", self.temp_files['ogg'], self.temp_files['wav']], 
                check=True
            )

            # Transcribir el audio (asumiendo que tienes esta función implementada)
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
    async def cleanup(self):
        """Limpia las conexiones"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()



    async def process_chat_message(self, message):
        """Procesa mensajes de chat"""
        await self.process_message(message, self.part_1_graph, CONFIG['queues']['incoming_chat'])

    async def process_audio_message_wrapper(self, message):
        """Procesa mensajes de audio"""
        await self.process_message(message, self.part_1_graph, CONFIG['queues']['incoming_audio'])

    async def start_consuming(self):
        """Inicia el consumo de mensajes"""
        while True:
            try:
                if not self.connection or self.connection.is_closed:
                    if not await self.connect():
                        await asyncio.sleep(5)
                        continue

                if not await self.setup_queues():
                    await asyncio.sleep(5)
                    continue

                # Declarar las colas utilizando la configuración especificada en CONFIG
                chat_queue = await self.channel.declare_queue(
                    CONFIG['queues']['incoming_chat'],
                    durable=True,
                    arguments=self.queue_args
                )
                
                audio_queue = await self.channel.declare_queue(

                    CONFIG['queues']['incoming_audio'],
                    durable=True,
                    arguments=self.queue_args
                )
                
                print("[*] Esperando mensajes. Presiona CTRL+C para salir")

                # Configurar consumidores en ambas colas
                await chat_queue.consume(self.process_chat_message)
                await audio_queue.consume(self.process_audio_message_wrapper)

                # Mantener el programa en ejecución
                await asyncio.Future()

            except Exception as e:
                print(f"Error en el consumidor: {e}")
                if self.connection and not self.connection.is_closed:
                    await self.connection.close()
                await asyncio.sleep(5)

    async def cleanup(self):
        """Limpia las conexiones"""
        if self.connection and not self.connection.is_closed():
            await self.connection.close()
