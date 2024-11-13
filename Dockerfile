# Usar la imagen base de Python
FROM python:3.11.9

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Crear directorio para la base de datos y establecer permisos
RUN mkdir -p /app/database && chmod 777 /app/database

# Copiar y instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Actualizar apt y preparar para la instalación de Node.js y supervisord
RUN apt-get update \
    && apt-get install -y curl supervisor ffmpeg default-libmysqlclient-dev pkg-config \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean


# Copiar los archivos package.json y package-lock.json e instalar dependencias de Node.js
COPY package*.json ./
RUN npm ci --only=production

# Copiar el archivo .env
COPY src/.env /app/.env

# Copiar el resto de la aplicación al contenedor
COPY . .

# Asegurar que la base de datos y su directorio tengan los permisos correctos
RUN chmod 777 /app/database

# Copiar el archivo de configuración de supervisord
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Exponer puertos necesarios
EXPOSE 3000 5000

# Definir el comando por defecto para ejecutar supervisord
CMD ["supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
    