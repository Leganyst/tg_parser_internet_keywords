#!/bin/sh
set -e

# Меняем владельца всех файлов на appuser (UID/GID)
chown -R appuser:appgroup /app

# Запускаем от appuser
exec su-exec appuser "$@"
