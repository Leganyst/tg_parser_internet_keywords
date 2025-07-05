FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники
COPY . .

# Для userbot: пробрасываем сессию наружу (чтобы не терялась при пересборке)
VOLUME ["/app"]

CMD ["python", "main.py"]
