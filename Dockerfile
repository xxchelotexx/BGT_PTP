# 1. IMAGEN BASE: Usa la etiqueta 'latest' de Jammy para obtener la versión más reciente y estable.
# Esto asegura que el entorno de Linux tenga todo lo que Playwright necesita.
FROM mcr.microsoft.com/playwright/python:jammy

# 2. DIRECTORIO DE TRABAJO
WORKDIR /app

# 3. INSTALAR DEPENDENCIAS DE PYTHON: Copia tu lista de requerimientos e instálalos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. COPIAR CÓDIGO
COPY . .

# 5. COMANDO DE INICIO
CMD ["python", "app.py"]