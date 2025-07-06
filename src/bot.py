from pyrogram import Client, filters
from loguru import logger
from src.config import API_ID, API_HASH, OWNER_ID, KEYWORDS_FILE, FUZZY_THRESHOLD
from src.keywords import load_keywords, add_keyword, remove_keyword
from src.utils import enhanced_find_match, smart_find_match, analyze_match_quality
from src.quality_monitor import quality_logger
import sys
import logging
import os

logger.remove()
logger.add(sys.stdout, level="DEBUG", format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}")

KEYWORDS = load_keywords(KEYWORDS_FILE)
MONITORED_CHAT_IDS = [] 

SESSION_FOLDER = os.path.join(os.getcwd(), "sessions")
os.makedirs(SESSION_FOLDER, exist_ok=True)


app = Client(
    name=os.path.join(SESSION_FOLDER, "userbot"),
    api_id=API_ID,
    api_hash=API_HASH
)

# --- Хэндлеры ---

def owner_filter(_, __, message):
    logger.debug(f"owner_filter: from_user={getattr(message, 'from_user', None)}")
    return message.from_user and message.from_user.id == OWNER_ID

@app.on_message(filters.command("start") & filters.private)
def start_handler(client, message):
    logger.info(f"/start от {message.from_user.id if message.from_user else 'N/A'}")
    message.reply_text("Бот запущен и работает.")

@app.on_message(filters.command("addword") & filters.create(owner_filter))
def add_word_handler(client, message):
    logger.info(f"/addword от {message.from_user.id if message.from_user else 'N/A'}: {message.text}")

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Укажите ключевое слово после команды.")
        return
    word = parts[1].strip()
    if add_keyword(word):
        logger.debug(f"Ключ добавлен: {word}")
        message.reply_text(f"Ключ '{word}' добавлен.")

        global KEYWORDS
        KEYWORDS = load_keywords("keywords.txt")
    else:
        logger.debug(f"Ключ не добавлен (уже есть или пусто): {word}")
        message.reply_text("Такой ключ уже есть или пустая строка.")

@app.on_message(filters.command("delword") & filters.create(owner_filter))
def del_word_handler(client, message):
    logger.info(f"/delword от {message.from_user.id if message.from_user else 'N/A'}: {message.text}")
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Укажите ключ для удаления.")
        return
    word = parts[1].strip()
    if remove_keyword(word):
        logger.debug(f"Ключ удалён: {word}")
        message.reply_text(f"Ключ '{word}' удалён.")
        global KEYWORDS
        KEYWORDS = load_keywords("keywords.txt")
    else:
        logger.debug(f"Ключ не найден для удаления: {word}")
        message.reply_text("Ключ не найден.")

@app.on_message(filters.command("showwords") & filters.create(owner_filter))
def show_words_handler(client, message):
    logger.info(f"/showwords от {message.from_user.id if message.from_user else 'N/A'}")
    keywords = load_keywords("keywords.txt")
    if not keywords:
        message.reply_text("Список ключей пуст.")
        return
    text = "\n".join(keywords)
    if len(text) > 4000:
        message.reply_text("Список слишком длинный для вывода.")
    else:
        message.reply_text(text)

@app.on_message(filters.command(["addword", "addkey"]) & filters.private & filters.me)
def add_word_self_handler(client, message):
    """
    Добавить ключевое слово через команду в избранных (или любом приватном чате от себя).
    Пример: /addword слово
    """
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Укажите ключевое слово после команды.\nПример: /addword интернет")
        return
    word = parts[1].strip()
    if add_keyword(word, KEYWORDS_FILE):
        message.reply_text(f"Ключ '{word}' добавлен.")
    else:
        message.reply_text("Такой ключ уже есть или пустая строка.")

@app.on_message(filters.command(["delword", "delkey"]) & filters.private & filters.me)
def del_word_self_handler(client, message):
    """
    Удалить ключевое слово через команду в избранных (или любом приватном чате от себя).
    Пример: /delword слово
    """
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        message.reply_text("Укажите ключ для удаления.\nПример: /delword интернет")
        return
    word = parts[1].strip()
    if remove_keyword(word, KEYWORDS_FILE):
        message.reply_text(f"Ключ '{word}' удалён.")
    else:
        message.reply_text("Ключ не найден.")

@app.on_message(filters.command(["showwords", "listkeys"]) & filters.private & filters.me)
def show_words_self_handler(client, message):
    """
    Показать все ключевые слова.
    """
    keywords = load_keywords(KEYWORDS_FILE)
    if not keywords:
        message.reply_text("Список ключей пуст.")
        return
    text = "\n".join(keywords)
    if len(text) > 4000:
        message.reply_text("Список слишком длинный для вывода.")
    else:
        message.reply_text(text)

@app.on_message(filters.command(["addwords", "addkeys"]) & filters.private & filters.me)
def add_words_bulk_handler(client, message):
    """
    Добавить сразу несколько ключевых слов (каждое с новой строки или через запятую).
    Пример:
    /addwords
    слово1
    слово2
    слово3
    или: /addwords слово1, слово2, слово3
    """
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        message.reply_text("Укажите ключевые слова после команды. Можно через запятую или с новой строки.")
        return
    words = text[1].replace(",", "\n").splitlines()
    added, skipped = [], []
    for word in words:
        w = word.strip()
        if w:
            if add_keyword(w, KEYWORDS_FILE):
                added.append(w)
            else:
                skipped.append(w)
    reply = []
    if added:
        reply.append(f"Добавлены: {', '.join(added)}")
    if skipped:
        reply.append(f"Пропущены (уже есть/пусто): {', '.join(skipped)}")
    message.reply_text("\n".join(reply) if reply else "Ничего не добавлено.")

@app.on_message(filters.command(["delwords", "delkeys"]) & filters.private & filters.me)
def del_words_bulk_handler(client, message):
    """
    Удалить сразу несколько ключевых слов (каждое с новой строки или через запятую).
    Пример:
    /delwords
    слово1
    слово2
    или: /delwords слово1, слово2
    """
    text = message.text.split(maxsplit=1)
    if len(text) < 2:
        message.reply_text("Укажите ключевые слова для удаления. Можно через запятую или с новой строки.")
        return
    words = text[1].replace(",", "\n").splitlines()
    removed, not_found = [], []
    for word in words:
        w = word.strip()
        if w:
            if remove_keyword(w, KEYWORDS_FILE):
                removed.append(w)
            else:
                not_found.append(w)
    reply = []
    if removed:
        reply.append(f"Удалены: {', '.join(removed)}")
    if not_found:
        reply.append(f"Не найдены: {', '.join(not_found)}")
    message.reply_text("\n".join(reply) if reply else "Ничего не удалено.")

@app.on_message(filters.command(["help", "start"]) & filters.private & filters.me)
def help_self_handler(client, message):
    """
    Справка по командам userbot.
    """
    help_text = (
        "Userbot: управление ключевыми словами через команды в избранных (Saved Messages) или в личке от себя.\n\n"
        "📝 Управление ключевыми словами:\n"
        "/addword <слово> — добавить ключ\n"
        "/delword <слово> — удалить ключ\n"
        "/addwords <слово1, слово2, ...> — добавить сразу несколько ключей (через запятую или с новой строки)\n"
        "/delwords <слово1, слово2, ...> — удалить сразу несколько ключей (через запятую или с новой строки)\n"
        "/showwords — показать все ключи\n\n"
        "📊 Мониторинг качества:\n"
        "/stats — показать статистику качества совпадений\n"
        "/clear_stats — очистить статистику\n\n"
        "/help — эта справка\n\n"
        "Пример: /addwords интернет, лаги, нет связи\n"
        "Или:\n/addwords\nинтернет\nлаги\nнет связи\n"
        "Все изменения сохраняются в файл keywords.txt."
    )
    message.reply_text(help_text)

@app.on_message(filters.command(["stats", "quality"]) & filters.private & filters.me)
def stats_handler(client, message):
    """
    Показать статистику качества совпадений
    """
    from src.quality_monitor import create_quality_report
    
    try:
        report = create_quality_report()
        
        # Разбиваем длинный отчет на части, если нужно
        if len(report) > 4000:
            parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
            for i, part in enumerate(parts):
                if i == 0:
                    message.reply_text(f"📊 Статистика качества (часть {i+1}/{len(parts)}):\n\n{part}")
                else:
                    message.reply_text(f"📊 Статистика качества (часть {i+1}/{len(parts)}):\n\n{part}")
        else:
            message.reply_text(f"📊 Статистика качества:\n\n{report}")
            
    except Exception as e:
        message.reply_text(f"Ошибка при генерации статистики: {str(e)}")

@app.on_message(filters.command("clear_stats") & filters.private & filters.me)
def clear_stats_handler(client, message):
    """
    Очистить статистику качества
    """
    import os
    
    log_file = "match_quality.log"
    if os.path.exists(log_file):
        os.remove(log_file)
        message.reply_text("📊 Статистика качества очищена.")
    else:
        message.reply_text("📊 Файл статистики не найден.")

@app.on_message(filters.text)
def all_messages_handler(client, message):
    logger.debug(f"all_messages_handler: chat_id={message.chat.id}, chat_type={message.chat.type}, user_id={getattr(message.from_user, 'id', None)}, text={message.text[:50] if message.text else ''}")
    # Можно фильтровать по chat_id, если нужно:
    # if MONITORED_CHAT_IDS and message.chat.id not in MONITORED_CHAT_IDS:
    #     return
    
    KEYWORDS = load_keywords(KEYWORDS_FILE)
    text = message.text or ""
    
    # Используем умный поиск с учетом контекста
    matched = smart_find_match(text, KEYWORDS, threshold=FUZZY_THRESHOLD)
    
    if matched:
        # Анализируем качество совпадения
        quality_metrics = analyze_match_quality(text, matched)
        
        # Логируем для мониторинга качества
        quality_logger.log_match(text, matched, quality_metrics, is_false_positive=False)
        
        logger.info(f"Совпадение: '{matched}' в чате {message.chat.id} ({message.chat.type}) "
                   f"[качество: {quality_metrics['confidence'] if quality_metrics else 'unknown'}]")
        
        notify_text = (
            f"🔔 Совпадение по ключу: '{matched}'\n"
            f"Чат: {message.chat.title or message.chat.id} ({message.chat.type})\n"
            f"Пользователь: {message.from_user.first_name if message.from_user else 'N/A'}\n"
            f"Текст:\n{text[:500]}"
        )
        
        # Добавляем информацию о качестве совпадения (опционально)
        if quality_metrics and quality_metrics['confidence'] == 'low':
            notify_text += f"\n⚠️ Низкая уверенность в совпадении"
        # Для супергрупп — ссылка на сообщение (только если есть message.id)
        if str(message.chat.id).startswith("-100") and hasattr(message, "id"):
            chat_id_num = str(message.chat.id)[4:]
            notify_text += f"\n[Открыть сообщение](https://t.me/c/{chat_id_num}/{message.id})"
        # Отправляем только в избранное (Saved Messages)
        client.send_message("me", notify_text, disable_web_page_preview=True)
        # Прямая пересылка сообщения, если возможно
        try:
            client.forward_messages("me", message.chat.id, message.id)
            logger.debug(f"Переслано сообщение {message.id} из чата {message.chat.id} в избранное.")
        except ValueError as e:
            if "Peer id invalid" in str(e):
                logger.warning(f"Ошибка пересылки: Peer id invalid ({message.chat.id}). Скорее всего, userbot не состоит в этом чате или Pyrogram не видит его в сессии. Пересылка невозможна. Подробнее: {e}")
            else:
                logger.warning(f"Ошибка пересылки сообщения: {e}")
        except Exception as e:
            logger.warning(f"Неизвестная ошибка пересылки сообщения: {e}")
