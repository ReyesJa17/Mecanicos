const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, downloadMediaMessage } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const amqp = require('amqplib'); // Cambiado a la versión Promise
const fs = require('fs').promises;
const ffmpeg = require('fluent-ffmpeg');
const tmp = require('tmp');
const path = require('path');
const P = require('pino');

const CONFIG = {
    rabbit: {
        user: process.env.RABBIT_USER || 'guest',
        password: process.env.RABBIT_PASSWORD || 'guest',
        host: process.env.RABBITMQ_HOST || 'localhost',
        reconnectDelay: 5000,
        maxRetries: 5,
        heartbeat: 60
    },
    app: {
        id: 'Mecanicos',
        queueConfig: {
            durable: true,
            arguments: {
                'x-message-ttl': 60000, // Volvemos al valor original de 60000
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



// Función principal mejorada para conectar a WhatsApp
async function connectToWhatsApp() {
    try {
        const authPath = path.join(__dirname, 'auth_info_baileys');
        const { state, saveCreds } = await useMultiFileAuthState(authPath);

        const startSocket = async () => {
            const sock = makeWASocket({
                auth: state,
                printQRInTerminal: true,
                retryRequestDelayMs: 2000,
                connectTimeoutMs: 60000,
                maxIdleTimeMs: 60000,
                defaultQueryTimeoutMs: 120000,
                logger: P({ level: 'warn' }), // Reducido a warn para menos ruido
                browser: ['WhatsApp Service', 'Chrome', '4.0.0'],
                keepAliveIntervalMs: 30000,
            });

            sock.ev.on('creds.update', saveCreds);
            setupConnectionHandler(sock, startSocket);
            setupMessageHandler(sock);

            return sock;
        };

        const sock = await startSocket();

        // Conectar a RabbitMQ con mejoras
        const rabbitmqUrl = `amqp://${CONFIG.rabbit.user}:${CONFIG.rabbit.password}@${CONFIG.rabbit.host}`;
        const connection = await amqp.connect(rabbitmqUrl, {
            heartbeat: CONFIG.rabbit.heartbeat
        });
        
        connection.on('error', async (error) => {
            console.error('Error en conexión RabbitMQ:', error);
            // Intentar reconectar
            setTimeout(connectToWhatsApp, CONFIG.rabbit.reconnectDelay);
        });

        const channel = await connection.createChannel();

        // Configurar las colas con manejo de errores
        for (const queue of Object.values(QUEUES)) {
            try {
                await channel.assertQueue(queue, CONFIG.app.queueConfig);
            } catch (error) {
                console.error(`Error al configurar cola ${queue}:`, error);
                // Continuar con las siguientes colas
            }
        }

        await setupMediaConsumer(channel, sock);
        await setupOutgoingConsumer(channel, sock);

        console.log('Sistema iniciado correctamente');
        
        // Manejo de errores no capturados
        process.on('uncaughtException', (error) => {
            console.error('Error no capturado:', error);
            // Continuar ejecutando
        });

        process.on('unhandledRejection', (reason, promise) => {
            console.error('Rechazo no manejado:', reason);
            // Continuar ejecutando
        });

    } catch (error) {
        console.error('Error al iniciar WhatsApp:', error);
        // Reintentar conexión
        setTimeout(connectToWhatsApp, CONFIG.rabbit.reconnectDelay);
    }
}


// Manejador de conexión mejorado
function setupConnectionHandler(sock, startSocket) {
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 10;

    sock.ev.on('connection.update', async (update) => {
        console.log('Actualización de conexión:', update);
        const { connection, lastDisconnect } = update;

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.output?.payload?.statusCode;

            console.error('Conexión cerrada:', lastDisconnect?.error);

            const shouldReconnect = statusCode !== DisconnectReason.loggedOut && statusCode !== DisconnectReason.connectionReplaced;

            if (shouldReconnect && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                console.log(`Reconectando (intento ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`);
                setTimeout(() => startSocket(), CONFIG.rabbit.reconnectDelay * Math.min(reconnectAttempts, 5));
            } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
                console.error('Máximo de intentos de reconexión alcanzado');
                // Puedes decidir si reiniciar la aplicación o no
            } else {
                console.log('Desconectado por conflicto o cierre de sesión. No se intentará reconectar.');
            }
        } else if (connection === 'open') {
            console.log('Conexión establecida con WhatsApp');
            reconnectAttempts = 0; // Resetear contador
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

            for (const msg of validMessages) {
                try {
                    await handleIncomingMessage(msg, sock);
                } catch (error) {
                    console.error('Error al procesar mensaje:', error);
                    // Continuar con el siguiente mensaje
                }
            }
        } catch (error) {
            console.error('Error al procesar mensajes:', error);
            // Continuar ejecutando
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
async function setupOutgoingConsumer(channel, sock) {
    const RETRY_DELAY = 5000;
    const MAX_RETRIES = 5;

    await channel.prefetch(1);

    channel.consume(QUEUES.outgoing, async (msg) => {
        if (!msg) return;

        const retryCount = (msg.properties.headers?.retryCount || 0);

        try {
            if (!sock?.user) {
                console.warn("Conexión a WhatsApp no lista. Reintentando en 5 segundos.");
                setTimeout(() => channel.nack(msg, false, true), RETRY_DELAY);
                return;
            }

            const data = JSON.parse(msg.content.toString());
            const { number, response, audio } = data;

            // En sendWithRetry, añadir comprobación de conexión
    const sendWithRetry = async (sendFn) => {
        let lastError;
        for (let i = 0; i < MAX_RETRIES; i++) {
            try {
                if (!sock?.user) {
                    console.warn("Conexión a WhatsApp no lista. Esperando 5 segundos...");
                    await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
                    continue; // Intentar de nuevo
                }
                await sendFn();
                return true;
            } catch (error) {
                lastError = error;
                if (i < MAX_RETRIES - 1) {
                    console.warn(`Error al enviar, reintentando (${i + 1}/${MAX_RETRIES})...`);
                    await new Promise(resolve => setTimeout(resolve, RETRY_DELAY * (i + 1)));
                }
            }
        }
        console.error(`Error al enviar después de ${MAX_RETRIES} intentos:`, lastError);
        return false;
    };


            // Detectar si es un documento Excel
            if (response && response.filename && response.content && 
                response.content_type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
                
                // Convertir el contenido base64 a buffer
                const documentBuffer = Buffer.from(response.content, 'base64');
                
                // Enviar el documento como archivo
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, {
                    document: documentBuffer,
                    mimetype: response.content_type,
                    fileName: response.filename
                }));
                
                console.log(`Documento Excel enviado a ${number}: ${response.filename}`);
            }

             // Manejar PDF
             if (response && response.filename && response.content && 
                response.content_type === 'application/pdf') {
                
                // Convertir el contenido base64 a buffer
                const pdfBuffer = Buffer.from(response.content, 'base64');
                
                // Enviar el PDF como archivo
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, {
                    document: pdfBuffer,
                    mimetype: 'application/pdf',  // MIME correcto para PDF
                    fileName: response.filename
                }));
                
                console.log(`PDF enviado a ${number}: ${response.filename}`);
            }


            // Manejar audio
            else if (audio) {
                const audioBuffer = Buffer.from(audio, 'base64');
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, {
                    audio: audioBuffer,
                    mimetype: 'audio/ogg; codecs=opus',
                    ptt: true
                }));
                console.log(`Audio enviado a ${number}`);
            } 
            // Manejar texto simple
            else if (response && typeof response === 'string') {
                await sendWithRetry(() => sock.sendMessage(`${number}@s.whatsapp.net`, { 
                    text: response 
                }));
                console.log(`Texto enviado a ${number}: ${response}`);
            }

            channel.ack(msg);

        } catch (error) {
            console.error('Error en consumidor de mensajes salientes:', {
                error: error.message,
                retryCount,
                messageId: msg.properties.messageId,
                payload: msg.content.toString().substring(0, 100) + '...' // Log parcial del payload para debugging
            });

            if (retryCount < MAX_RETRIES) {
                setTimeout(async () => {
                    try {
                        await channel.publish('', QUEUES.outgoing, msg.content, {
                            persistent: true,
                            headers: {
                                retryCount: retryCount + 1
                            }
                        });
                        channel.ack(msg);
                    } catch (pubError) {
                        console.error('Error al republicar mensaje:', pubError);
                        channel.nack(msg, false, true);
                    }
                }, RETRY_DELAY);
            } else {
                console.error(`Mensaje descartado después de ${MAX_RETRIES} intentos para ${msg.properties.messageId}`);
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
// Inicio de la aplicación con reintentos
connectToWhatsApp().catch(error => {
    console.error('Error inicial:', error);
    setTimeout(connectToWhatsApp, CONFIG.rabbit.reconnectDelay);
});