# parse_internet_words

Userbot на Pyrogram для мониторинга ключевых слов в любых чатах Telegram.

## Возможности
- Чтение сообщений из всех чатов, групп, супергрупп, каналов (userbot).
- Поиск по ключевым словам (fuzzy и точное совпадение).
- Уведомления и пересылка совпавших сообщений в "Избранное" (Saved Messages).
- Управление ключевыми словами через команды.

## Быстрый старт

1. Склонируйте репозиторий:
   ```sh
   git clone ...
   cd parse_intertet_words
   ```
2. Заполните `.env` (пример в `.env.example`).
   - Для userbot BOT_TOKEN не нужен, но может быть в .env — он игнорируется.
   - Укажите KEYWORDS_FILE=src/keywords.txt
3. Добавьте ключевые слова в `src/keywords.txt` (по одному на строку).
4. Соберите и запустите Docker:
   ```sh
   docker build -t parse_internet_words .
   docker run --rm -it \
     -v $(pwd)/src:/app/src \
     -v $(pwd)/src/keywords.txt:/app/src/keywords.txt \
     -v $(pwd)/userbot.session:/app/userbot.session \
     --env-file .env \
     parse_internet_words
   ```
   > При первом запуске потребуется ввести код из Telegram для авторизации userbot.

5. Для запуска без Docker:
   ```sh
   python -m src.main
   ```

## Структура
- `src/` — исходный код (модули, main, логика)
- `src/keywords.txt` — ключевые слова
- `.env` — переменные окружения
- `userbot.session` — сессия Pyrogram (userbot)

## Примечания
- Для userbot требуется авторизация по номеру телефона при первом запуске.
- Все уведомления и пересылки идут только в "Избранное".
- Для обновления ключевых слов — просто редактируйте `src/keywords.txt`.
- BOT_TOKEN не используется для userbot, но может быть в .env для совместимости.

---

**Проект полностью готов к деплою на сервер через Docker.**
