# 1. Usar una imagen base de Playwright que incluye navegadores y dependencias.
# Esto asegura que el entorno de Linux tenga todo lo que Playwright necesita.
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# 2. Establecer el directorio de trabajo
WORKDIR /app

# 3. Copiar e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar el resto del código
COPY . .

# 5. Comando para iniciar la aplicación (usa el puerto $PORT de Railway)
# Usamos un comando estándar de Python para iniciar tu app.py
# El servidor de desarrollo de Flask no es ideal para producción, 
# pero es el comando más simple.
CMD ["python", "app.py"]