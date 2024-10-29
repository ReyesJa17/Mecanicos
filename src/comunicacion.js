const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const amqp = require('amqplib'); // Cambiado a la versión Promise
const fs = require('fs').promises;
const ffmpeg = require('fluent-ffmpeg');
const tmp = require('tmp');
const path = require('path');
const P = require('pino');

// Configuración
const CONFIG = {
    rabbit: {
        user: 'guest',
        password: 'guest',
        host: 'localhost',
        reconnectDelay: 5000,
        maxRetries: 5
    },
    app: {
        id: 'Mecanicos',
        queueConfig: {
            durable: true,
            arguments: {
                'x-message-ttl': 60000,
                'x-max-length': 1000
            }
        }
    }
};

// Nombres de colas
const QUEUES = {
    outgoing: `${CONFIG.app.id}-respuesta-Bot`,
    incomingChat: `${CONFIG.app.id}-chat`,
    incomingAudio: `${CONFIG.app.id}-audio`,
    media: `${CONFIG.app.id}-Tool-Media`
};

// Función principal para conectar a WhatsApp
async function connectToWhatsApp() {
    try {
        const authPath = path.join(__dirname, 'auth_info_baileys');
        const { state, saveCreds } = await useMultiFileAuthState(authPath);

        const startSocket = async () => {
            const sock = makeWASocket({
                auth: state,
                printQRInTerminal: true,
                retryRequestDelayMs: 2000,
                connectTimeoutMs: 30000,
                maxIdleTimeMs: 60000,
                defaultQueryTimeoutMs: 120000,
                logger: P({ level: 'debug' })
            });

            sock.ev.on('creds.update', saveCreds);
            setupConnectionHandler(sock, startSocket);
            setupMessageHandler(sock);

            return sock;
        };

        const sock = await startSocket();

        // Conectar a RabbitMQ usando promesas
        const rabbitmqUrl = `amqp://${CONFIG.rabbit.user}:${CONFIG.rabbit.password}@${CONFIG.rabbit.host}`;
        const connection = await amqp.connect(rabbitmqUrl);
        const channel = await connection.createChannel();

        // Configurar las colas
        await Promise.all(
            Object.values(QUEUES).map(queue =>
                channel.assertQueue(queue, CONFIG.app.queueConfig)
            )
        );

        await setupMediaConsumer(channel, sock);
        await setupOutgoingConsumer(channel, sock);

        console.log('Sistema iniciado correctamente');
    } catch (error) {
        console.error('Error al iniciar WhatsApp:', error);
        process.exit(1);
    }
}

// Manejador de conexión
function setupConnectionHandler(sock, startSocket) {
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect } = update;

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

            console.error('Conexión cerrada:', lastDisconnect?.error);

            if (shouldReconnect) {
                console.log(`Reconectando en ${CONFIG.rabbit.reconnectDelay / 1000} segundos...`);
                setTimeout(() => startSocket(), CONFIG.rabbit.reconnectDelay);
            } else {
                console.log('Sesión finalizada. Por favor, escanee el código QR nuevamente.');
            }
        } else if (connection === 'open') {
            console.log('Conexión establecida con WhatsApp');
        }
    });
}

// Manejador de mensajes
function setupMessageHandler(sock) {
    sock.ev.on('messages.upsert', async ({ messages }) => {
        try {
            const validMessages = messages.filter(msg =>
                !msg.key.fromMe &&
                msg.key.remoteJid?.endsWith('@s.whatsapp.net')
            );

            await Promise.all(validMessages.map(msg => handleIncomingMessage(msg, sock)));
        } catch (error) {
            console.error('Error al procesar mensajes:', error);
        }
    });
}

// Procesamiento de mensajes entrantes
async function handleIncomingMessage(msg, sock) {
    try {
        const numberId = msg.key.remoteJid;
        const number = numberId.split('@')[0];

        if (msg.message?.audioMessage) {
            await handleAudioMessage(msg, number, sock);
        } else {
            const textMessage = extractMessageContent(msg);
            if (textMessage) {
                console.log(`Mensaje de texto recibido de ${number}: ${textMessage}`);
                await sendToRabbitMQ(number, textMessage, QUEUES.incomingChat);
            }
        }
    } catch (error) {
        console.error('Error en handleIncomingMessage:', error);
    }
}

// Procesamiento de mensajes de audio
async function handleAudioMessage(msg, number, sock) {
    let tempInputFile = null;
    let tempOutputFile = null;

    try {
        const audioStream = await downloadMediaMessage(msg, 'buffer', {}, {
            logger: sock.logger,
            reuploadRequest: sock.updateMediaMessage
        });

        if (!audioStream?.length) {
            throw new Error('Stream de audio vacío');
        }

        tempInputFile = tmp.fileSync({ postfix: '.opus' });
        tempOutputFile = tmp.fileSync({ postfix: '.opus' });

        await fs.writeFile(tempInputFile.name, audioStream);

        await new Promise((resolve, reject) => {
            ffmpeg(tempInputFile.name)
                .audioFrequency(16000)
                .audioBitrate('64k')
                .audioChannels(1)
                .toFormat('opus')
                .on('error', reject)
                .on('end', resolve)
                .save(tempOutputFile.name);
        });

        const convertedAudio = await fs.readFile(tempOutputFile.name);
        await sendToRabbitMQ(number, convertedAudio, QUEUES.incomingAudio, true);

        console.log(`Audio procesado para ${number}`);
    } catch (error) {
        console.error('Error al procesar audio:', error);
        throw error;
    } finally {
        tempInputFile?.removeCallback();
        tempOutputFile?.removeCallback();
    }
}

// Utilidades
function extractMessageContent(msg) {
    return msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        null;
}

// Consumidor de mensajes salientes
async function setupOutgoingConsumer(channel, sock) {
    const RETRY_DELAY = 5000; // 5 segundos
    const MAX_RETRIES = 3;

    // Asegurarse de que solo procesamos un mensaje a la vez
    await channel.prefetch(1);

    // Configurar el consumidor
    channel.consume(QUEUES.outgoing, async (msg) => {
        if (!msg) return;

        // Obtener o inicializar el contador de reintentos
        const retryCount = (msg.properties.headers?.retryCount || 0);

        try {
            // Verificar el estado de la conexión
            if (!sock.user) {
                throw new Error('WhatsApp connection not ready');
            }

            const data = JSON.parse(msg.content.toString());
            const { number, response, audio } = data;

            // Función de utilidad para reintentos de envío
            const sendWithRetry = async (sendFn) => {
                let lastError;
                for (let i = 0; i < 3; i++) {
                    try {
                        await sendFn();
                        return true;
                    } catch (error) {
                        lastError = error;
                        if (i < 2) { // No esperar en el último intento
                            await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
                        }
                    }
                }
                throw lastError;
            };

            if (audio) {
                const audioBuffer = Buffer.from(audio, 'base64');
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, {
                    audio: audioBuffer,
                    mimetype: 'audio/ogg; codecs=opus',
                    ptt: true
                }));
                console.log(`Audio enviado a ${number}`);
            } else if (response) {
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, { 
                    text: response 
                }));
                console.log(`Texto enviado a ${number}: ${response}`);
            }

            // Si llegamos aquí, el mensaje se envió correctamente
            channel.ack(msg);

        } catch (error) {
            console.error('Error en consumidor de mensajes salientes:', {
                error: error.message,
                retryCount,
                messageId: msg.properties.messageId
            });

            if (retryCount < MAX_RETRIES) {
                // Republicar el mensaje con contador de reintentos incrementado
                setTimeout(async () => {
                    try {
                        await channel.publish('', QUEUES.outgoing, msg.content, {
                            persistent: true,
                            headers: {
                                retryCount: retryCount + 1
                            }
                        });
                        // Confirmar el mensaje original después de republicarlo
                        channel.ack(msg);
                    } catch (pubError) {
                        console.error('Error al republicar mensaje:', pubError);
                        channel.nack(msg, false, true);
                    }
                }, RETRY_DELAY);
            } else {
                console.error(`Mensaje descartado después de ${MAX_RETRIES} intentos para ${msg.properties.messageId}`);
                // Aquí podrías implementar una lógica para mover el mensaje a una cola de mensajes muertos
                channel.ack(msg);
            }
        }
    }, {
        noAck: false
    });

    console.log('Consumidor de mensajes salientes configurado exitosamente');
}




// Consumidor de mensajes de media
// Consumidor mejorado de mensajes de media con más logs

async function setupMediaConsumer(channel, sock) {
    console.log('Configurando consumidor de media...');
    
    channel.consume(QUEUES.media, async (msg) => {
        if (!msg || !msg.content) {
            console.error('ERROR: Mensaje inválido recibido');
            if (msg) channel.nack(msg, false, false);
            return;
        }

        try {
            // Parsear el mensaje
            const content = msg.content.toString();
            const parsedContent = JSON.parse(content);

            // Validar campos esenciales
            if (!parsedContent.number || !parsedContent.data || !parsedContent.data_type) {
                throw new Error('Mensaje incompleto: faltan campos requeridos');
            }

            const { number, data, data_type, appId } = parsedContent;

            // Crear buffer desde base64
            const mediaBuffer = Buffer.from(data, 'base64');
            if (mediaBuffer.length === 0) {
                throw new Error('Buffer de media vacío');
            }

            // Preparar mensaje según el tipo
            let whatsappMsg;
            if (data_type === 'video') {
                whatsappMsg = {
                    video: mediaBuffer
                };
            } else if (data_type === 'image') {
                whatsappMsg = {
                    image: mediaBuffer
                };
            } else {
                throw new Error('Tipo de media no soportado');
            }

            // Enviar mensaje
            await sock.sendMessage(`${number}@s.whatsapp.net`, whatsappMsg);
            console.log(`${data_type} enviado correctamente a ${number}`);

            // Confirmar procesamiento exitoso
            channel.ack(msg);

        } catch (error) {
            console.error('Error en procesamiento de media:', {
                error: error.message,
                stack: error.stack
            });

            // Determinar si el error es permanente
            const isPermanentError = [
                'Mensaje incompleto',
                'Buffer de media vacío',
                'Tipo de media no soportado'
            ].some(errMsg => error.message.includes(errMsg));

            // Rechazar el mensaje según el tipo de error
            channel.nack(msg, false, !isPermanentError);
        }
    });

    console.log('Consumidor de media configurado exitosamente');
}




// Función para enviar mensajes a RabbitMQ
async function sendToRabbitMQ(number, content, queueName, isAudio = false) {
    const rabbitmqUrl = `amqp://${CONFIG.rabbit.user}:${CONFIG.rabbit.password}@${CONFIG.rabbit.host}`;
    let connection;

    try {
        connection = await amqp.connect(rabbitmqUrl);
        const channel = await connection.createChannel();

        const message = isAudio
            ? { number, audio: content.toString('base64') }
            : { number, textMessage: content };

        await channel.assertQueue(queueName, CONFIG.app.queueConfig);
        await channel.sendToQueue(queueName, Buffer.from(JSON.stringify(message)));

        console.log(`Mensaje enviado a ${queueName}`);
    } catch (error) {
        console.error(`Error al enviar a ${queueName}:`, error);
        throw error;
    } finally {
        if (connection) {
            setTimeout(() => connection.close(), 500);
        }
    }
}

// Iniciar la aplicación
connectToWhatsApp().catch(console.error);