FROM python:3.11-slim

ARG UID=1000
ARG GID=1000

RUN addgroup --gid $GID appgroup && \
    adduser --disabled-password --gecos '' --uid $UID --gid $GID appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER appuser

CMD ["python", "main.py"]
