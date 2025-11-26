# Cambia la etiqueta de la versión para que coincida con la requerida por tu librería de Playwright
FROM mcr.microsoft.com/playwright/python:v1.56.0-jammy 

# 2. DIRECTORIO DE TRABAJO
WORKDIR /app

# 3. INSTALAR DEPENDENCIAS DE PYTHON: Copia tu lista de requerimientos e instálalos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. COPIAR CÓDIGO
COPY . .

# 5. COMANDO DE INICIO
CMD ["python", "app.py"]