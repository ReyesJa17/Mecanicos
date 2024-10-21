// Importar las librerías necesarias
const { makeWASocket, DisconnectReason, useMultiFileAuthState, downloadMediaMessage } = require('@whiskeysockets/baileys');
const fs = require('fs');
const path = require('path');
const ffmpeg = require('fluent-ffmpeg');
const streamifier = require('streamifier');
const amqp = require('amqplib/callback_api');
const tmp = require('tmp'); // Mover esta línea aquí

// Configuración de conexión a RabbitMQ
const RABBIT_USER = 'guest';
const RABBIT_PASSWORD = 'guest';
const RABBIT_HOST = 'localhost';

// Función para conectarse a WhatsApp y manejar mensajes entrantes
async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState('auth_info_baileys');

    const startSocket = () => {
        const sock = makeWASocket({
            auth: state,
            printQRInTerminal: true
        });

        sock.ev.on('creds.update', saveCreds);

        sock.ev.on('connection.update', (update) => {
            const { connection, lastDisconnect } = update;
            if (connection === 'close') {
                const statusCode = (lastDisconnect?.error)?.output?.statusCode;
                const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
                console.error('Conexión cerrada:', lastDisconnect?.error);
                if (shouldReconnect) {
                    console.log('Intentando reconectar...');
                    setTimeout(() => startSocket(), 5000);  // Agregar una pausa antes de intentar reconectar
                } else {
                    console.log('Error 401: Necesita volver a escanear el QR.');
                }
            } else if (connection === 'open') {
                console.log('Conectado exitosamente a WhatsApp');
            }
        });

        sock.ev.on('messages.upsert', async ({ messages, type }) => {
            if (type === 'notify') {
                for (const message of messages) {
                    if (!message.message) return;

                    let messageType = Object.keys(message.message)[0];
                    const jid = message.key.remoteJid;
                    const number = jid.split('@')[0]; // Extraer el número sin el sufijo

                    console.log(`Mensaje recibido de ${jid}:`, message.message);

                    // Manejar mensajes según su tipo
                    if (messageType === 'conversation' || messageType === 'extendedTextMessage') {
                        // Enviar mensajes de texto a la cola Mecanicos-chat
                        const text = message.message.conversation || message.message.extendedTextMessage.text;
                        sendToRabbitMQ(number, text, 'Mecanicos-chat');
                    } else if (['audioMessage'].includes(messageType)) {
                        // Manejar los audios y enviarlos a la cola Mecanicos-audios
                        await handleMediaMessage(sock, message, messageType, number);
                    } else {
                        console.log(`Tipo de mensaje no soportado: ${messageType}`);
                    }
                }
            }
        });

        // Añadir esta línea para comenzar a recibir mensajes de RabbitMQ
        receiveFromRabbitMQ(sock);
    };

    startSocket();
}

async function handleMediaMessage(sock, message, messageType, number) {
    const mediaMessage = message.message[messageType];

    try {
        // Descargar el mensaje de medios
        console.log('Intentando descargar el mensaje de audio...');
        const stream = await downloadMediaMessage(message, 'buffer', {}, {
            logger: sock.logger,
            reuploadRequest: sock.updateMediaMessage
        });

        if (!stream || stream.length === 0) {
            console.error('Error: La descarga del mensaje de audio devolvió un stream vacío.');
            return;
        }

        console.log('Audio descargado con éxito. Tamaño del buffer:', stream.length);

        // Si es un audioMessage, convertir a OGG en memoria y enviar a RabbitMQ
        if (messageType === 'audioMessage') {
            convertOpusToOggInMemory(stream, (oggBuffer) => {
                if (oggBuffer && oggBuffer.length > 0) {
                    sendToRabbitMQ(number, oggBuffer, 'Mecanicos-audios');
                } else {
                    console.error('Error: El buffer de audio convertido está vacío.');
                }
            });
        } else {
            console.log(`${messageType} recibido, pero sin procesamiento adicional.`);
        }
    } catch (error) {
        console.error('Error al descargar el archivo:', error);
    }
}

function convertOpusToOggInMemory(opusBuffer, callback) {
    if (!opusBuffer || opusBuffer.length === 0) {
        console.error('Error: El buffer de audio opus está vacío antes de la conversión.');
        return;
    }

    console.log('Iniciando la conversión de Opus a OGG. Tamaño del buffer:', opusBuffer.length);

    // Crear un archivo temporal para el buffer opus
    const tempInputFile = tmp.tmpNameSync({ postfix: '.ogg' });
    fs.writeFileSync(tempInputFile, opusBuffer);
    const tempOutputFile = tmp.tmpNameSync({ postfix: '.ogg' });

    ffmpeg(tempInputFile)
        .inputFormat('ogg') // Especificar el formato de entrada como OGG
        .toFormat('opus')
        .audioCodec('libopus')
        .on('start', (commandLine) => {
            console.log('Comando de ffmpeg:', commandLine);
        })
        .on('error', (err) => {
            console.error('Error al convertir archivo opus a ogg:', err);
            callback(null);
        })
        .on('end', () => {
            console.log('Archivo convertido a OGG Opus y guardado en un archivo temporal.');

            // Leer el archivo de salida y pasarlo como buffer a callback
            const oggBuffer = fs.readFileSync(tempOutputFile);
            if (oggBuffer.length > 0) {
                console.log('Tamaño del buffer OGG:', oggBuffer.length);
                callback(oggBuffer);
            } else {
                console.error('Error: No se generaron datos de salida durante la conversión.');
                callback(null);
            }

            // Eliminar archivos temporales
            fs.unlinkSync(tempInputFile);
            fs.unlinkSync(tempOutputFile);
        })
        .save(tempOutputFile); // Guardar la salida en un archivo temporal
}

function sendToRabbitMQ(number, userMessage, queueName) {
    amqp.connect(`amqp://${RABBIT_USER}:${RABBIT_PASSWORD}@${RABBIT_HOST}`, (error0, connection) => {
        if (error0) {
            console.error('Conexión a RabbitMQ fallida:', error0.message);
            return;
        }
        console.log(`Conexión exitosa al servidor RabbitMQ para enviar mensajes a la cola ${queueName}.`);

        connection.createChannel((error1, channel) => {
            if (error1) {
                console.error('Fallo al crear el canal:', error1.message);
                connection.close();  // Asegúrate de cerrar la conexión si no se pudo crear el canal
                return;
            }
            console.log(`Canal creado exitosamente para enviar mensajes a la cola ${queueName}.`);

            // Crear el mensaje a enviar
            let message;
            if (queueName === 'Mecanicos-audios') {
                if (userMessage && userMessage.length > 0) {
                    try {
                        const audioBase64 = userMessage.toString('base64');
                        if (audioBase64.length === 0) {
                            console.error('Error: El buffer de audio está vacío después de convertirlo a base64.');
                            return;
                        }
                        console.log('Contenido del audio en base64:', audioBase64.slice(0, 100), '...'); // Mostrar los primeros 100 caracteres para verificar
                        message = JSON.stringify({ number, audio: audioBase64 });
                    } catch (error) {
                        console.error('Error al convertir el buffer de audio a base64:', error.message);
                        return;
                    }
                } else {
                    console.error('Error: Buffer de audio está vacío o no se ha proporcionado.');
                    return;
                }
            } else if (queueName === 'Mecanicos-chat') {
                message = JSON.stringify({ number, textMessage: userMessage });
            }

            // Verificar el mensaje antes de enviarlo
            if (!message) {
                console.error('Error: No se pudo generar el mensaje a enviar.');
                return;
            }

            channel.assertQueue(queueName, { durable: true });
            channel.sendToQueue(queueName, Buffer.from(message), {}, (err, ok) => {
                if (err) {
                    console.error('Error al enviar mensaje a RabbitMQ:', err);
                } else {
                    console.log(`Mensaje enviado a RabbitMQ en la cola ${queueName}: ${message}`);
                }

                // Cerrar el canal y la conexión solo después de enviar el mensaje correctamente
                setTimeout(() => {
                    channel.close();
                    connection.close();
                    console.log('Conexión a RabbitMQ cerrada después de enviar el mensaje.');
                }, 500);
            });
        });
    });
}

function receiveFromRabbitMQ(sock) {
    const queueName = 'Mecanicos-respuesta-Bot';
    const connectionString = `amqp://${RABBIT_USER}:${RABBIT_PASSWORD}@${RABBIT_HOST}`;

    amqp.connect(connectionString, (error0, connection) => {
        if (error0) {
            console.error('Conexión a RabbitMQ fallida:', error0.message);
            return;
        }
        console.log('Conexión exitosa al servidor RabbitMQ para recibir mensajes.');

        connection.createChannel((error1, channel) => {
            if (error1) {
                console.error('Fallo al crear el canal:', error1.message);
                return;
            }
            console.log('Canal creado exitosamente para recibir mensajes.');

            channel.assertQueue(queueName, { durable: true });
            channel.prefetch(1); // Procesar un mensaje a la vez para reducir el riesgo de sobrecarga

            channel.consume(queueName, async (msg) => {
                if (msg !== null) {
                    try {
                        const parsedMessage = JSON.parse(msg.content.toString());
                        let { number, response, audio } = parsedMessage;

                        // Validar el número y formatearlo correctamente
                        if (number && typeof number === 'string') {
                            if (number.includes('@')) {
                                number = number.split('@')[0];
                            }

                            const jid = `${number}@s.whatsapp.net`;

                            if (response) {
                                console.log(`Respuesta recibida para ${jid}: ${response}`);
                                await sock.sendMessage(jid, { text: response });
                            } else if (audio) {
                                console.log(`Enviando audio a ${jid}`);
                                const audioBuffer = Buffer.from(audio, 'base64');

                                // Verificar el tamaño del archivo
                                if (audioBuffer.length > 16 * 1024 * 1024) {
                                    console.error('Error: El archivo de audio excede el tamaño máximo permitido por WhatsApp.');
                                } else {
                                    await sock.sendMessage(jid, {
                                        audio: audioBuffer,
                                        mimetype: 'audio/ogg; codecs=opus',
                                        ptt: true
                                    });
                                }
                            } else {
                                console.error('Error: El mensaje recibido no contiene una respuesta ni un audio.');
                            }
                        } else {
                            console.error('Error: El número recibido no es válido.');
                        }

                        // Acknowledge el mensaje después de procesarlo
                        channel.ack(msg);

                    } catch (e) {
                        console.error('Error al parsear el mensaje:', e.message);
                        // Si hay un error al parsear el mensaje, se rechaza sin reencolar
                        channel.nack(msg, false, false);
                    }
                }
            });

            // Manejar la desconexión del canal de manera segura
            connection.on('error', (err) => {
                console.error('Conexión a RabbitMQ perdió la conexión:', err.message);
                channel.close();
                connection.close();
            });

            connection.on('close', () => {
                console.log('Conexión a RabbitMQ cerrada.');
            });
        });
    });
}

// Iniciar la conexión a WhatsApp
connectToWhatsApp();
