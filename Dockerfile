FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходники
COPY src ./src
COPY keywords.txt ./keywords.txt
COPY .env .env

# Для userbot: пробрасываем сессию наружу (чтобы не терялась при пересборке)
VOLUME ["/app"]

CMD ["python", "-m", "src.main"]
