# Usar una imagen base de Python
FROM python:3.13.0

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar el archivo requirements.txt y instalar las dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación
COPY . .

# Exponer el puerto en el que la aplicación correrá
EXPOSE 8000

# Comando para ejecutar la aplicación
ENTRYPOINT ["./entrypoint.sh"]