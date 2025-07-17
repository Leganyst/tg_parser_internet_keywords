from pyrogram import Client, filters
from loguru import logger
from src.config import API_ID, API_HASH, OWNER_ID, KEYWORDS_FILE, FUZZY_THRESHOLD, SPAM_FILE
from src.keywords import load_keywords, add_keyword, remove_keyword, load_spam_patterns, add_spam_pattern, remove_spam_pattern
from src.utils import simple_keyword_match
import sys
import logging
import os

logger.remove()
logger.add(sys.stdout, level="DEBUG", format="[{time:YYYY-MM-DD HH:mm:ss}] [{level}] {message}")

def load_keywords_safe(file_path):
    try:
        return load_keywords(file_path)
    except UnicodeDecodeError as e:
        logger.error(f"Ошибка декодирования файла {file_path}: {e}")
        return []

KEYWORDS = load_keywords(KEYWORDS_FILE)

PENDING_ACTIONS = {}

# --- Хэндлеры ---

async def owner_filter(_, __, message):
    logger.debug(f"owner_filter: from_user={getattr(message, 'from_user', None)}")
    return message.from_user and message.from_user.id == OWNER_ID

def register_handlers(app: Client):
    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client, message):
        logger.info(f"/start от {message.from_user.id if message.from_user else 'N/A'} в чате {message.chat.id}")
        await message.reply_text("Бот запущен и работает.")

    @app.on_message(filters.command("addword") & filters.create(owner_filter))
    async def add_word_handler(client, message):
        logger.info(f"/addword от {message.from_user.id if message.from_user else 'N/A'} в чате {message.chat.id}: {message.text}")

        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            logger.warning("Ключевое слово не указано после команды /addword.")
            await message.reply_text("Укажите ключевое слово после команды.")
            return
        word = parts[1].strip()
        if add_keyword(word, KEYWORDS_FILE):
            logger.debug(f"Ключ добавлен: {word}")
            await message.reply_text(f"Ключ '{word}' добавлен.")

            global KEYWORDS
            KEYWORDS = load_keywords(KEYWORDS_FILE)
        else:
            logger.warning(f"Ключ не добавлен (уже есть или пусто): {word}")
            await message.reply_text("Такой ключ уже есть или пустая строка.")

    @app.on_message(filters.command("delword") & filters.create(owner_filter))
    async def del_word_handler(client, message):
        logger.info(f"/delword от {message.from_user.id if message.from_user else 'N/A'} в чате {message.chat.id}: {message.text}")
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            logger.warning("Ключ для удаления не указан после команды /delword.")
            await message.reply_text("Укажите ключ для удаления.")
            return
        word = parts[1].strip()
        if remove_keyword(word, KEYWORDS_FILE):
            logger.debug(f"Ключ удалён: {word}")
            await message.reply_text(f"Ключ '{word}' удалён.")
            global KEYWORDS
            KEYWORDS = load_keywords(KEYWORDS_FILE)
        else:
            logger.warning(f"Ключ не найден для удаления: {word}")
            await message.reply_text("Ключ не найден.")

    @app.on_message(filters.command("showwords") & filters.create(owner_filter))
    async def show_words_handler(client, message):
        logger.info(f"/showwords от {message.from_user.id if message.from_user else 'N/A'} в чате {message.chat.id}")
        keywords = load_keywords(KEYWORDS_FILE)
        if not keywords:
            logger.info("Список ключей пуст.")
            await message.reply_text("Список ключей пуст.")
            return
        
        text_lines = [f"{i+1}. {keyword}" for i, keyword in enumerate(keywords)]
        full_text = f"📝 Список ключевых слов ({len(keywords)} шт.):\n\n" + "\n".join(text_lines)
        
        if len(full_text) > 4000:
            logger.info("Список ключей слишком длинный, разбиваем на части.")
            await message.reply_text(f"📝 Список ключевых слов ({len(keywords)} шт.):")
            chunk_size = 50
            for i in range(0, len(keywords), chunk_size):
                chunk = keywords[i:i+chunk_size]
                chunk_lines = [f"{i+j+1}. {keyword}" for j, keyword in enumerate(chunk)]
                chunk_text = f"Часть {i//chunk_size + 1}:\n" + "\n".join(chunk_lines)
                await message.reply_text(chunk_text)
        else:
            await message.reply_text(full_text)

    @app.on_message(filters.command("showspam") & filters.create(owner_filter))
    async def show_spam_handler(client, message):
        """Показать все спам-шаблоны"""
        patterns = load_spam_patterns(SPAM_FILE)
        if not patterns:
            await message.reply_text("Список спам-шаблонов пуст.")
            return
        text = "🛑 Шаблоны спама:\n" + "\n".join(f"{i+1}. {p}" for i,p in enumerate(patterns))
        await message.reply_text(text)
    
    @app.on_message(filters.command("showgroups") & filters.create(owner_filter))
    async def show_groups_handler(client, message):
        """Показать все паттерны групп и их название"""
        from src.group_map import load_group_map
        gm = load_group_map()
        if not gm:
            await message.reply_text("Список групп пуст.")
            return
        lines = [f"{i+1}. {pat} -> {grp}" for i,(pat,grp) in enumerate(gm.items())]
        await message.reply_text("Группы шаблонов:\n" + "\n".join(lines))

    @app.on_message(filters.command("addgroup") & filters.create(owner_filter))
    async def add_group_handler(client, message):
        """Добавить шаблон и группу: /addgroup паттерн|группа"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2 or '|' not in parts[1]:
            await message.reply_text("Использование: /addgroup шаблон|группа")
            return
        pattern, grp = [p.strip() for p in parts[1].split('|',1)]
        from src.group_map import add_group_pattern
        if add_group_pattern(pattern, grp):
            await message.reply_text(f"Добавлен паттерн '{pattern}' в группу '{grp}'")
        else:
            await message.reply_text("Не удалось добавить (возможно уже есть или пусто).")

    @app.on_message(filters.command("delgroup") & filters.create(owner_filter))
    async def del_group_handler(client, message):
        """Удалить шаблон из групп: /delgroup шаблон"""
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Использование: /delgroup шаблон")
            return
        pattern = parts[1].strip()
        from src.group_map import remove_group_pattern
        if remove_group_pattern(pattern):
            await message.reply_text(f"Удалён паттерн '{pattern}'")
        else:
            await message.reply_text("Паттерн не найден.")

    @app.on_message(filters.command("addgroups") & filters.create(owner_filter))
    async def add_groups_init_handler(client, message):
        """FSM: инициализация массового добавления group_map"""
        PENDING_ACTIONS[message.from_user.id] = 'ADD_GROUPS'
        await message.reply_text(
            "Пришлите шаблоны для добавления в формате 'паттерн|группа',\n" \
            "каждый с новой строки или через запятую."
        )

    @app.on_message(filters.text & filters.create(lambda _,__,msg: PENDING_ACTIONS.get(msg.from_user.id)=='ADD_GROUPS'))
    async def add_groups_fsm_handler(client, message):
        from src.group_map import add_group_pattern
        text = message.text
        parts = [p.strip() for p in text.replace(',', '\n').splitlines() if p.strip()]
        added, skipped = [], []
        for line in parts:
            if '|' not in line:
                skipped.append(line)
                continue
            pat, grp = [x.strip() for x in line.split('|',1)]
            if add_group_pattern(pat, grp):
                added.append(pat)
            else:
                skipped.append(pat)
        reply = []
        if added:
            reply.append(f"Добавлены: {', '.join(added)}")
        if skipped:
            reply.append(f"Пропущены: {', '.join(skipped)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не добавлено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)

    @app.on_message(filters.command("delgroups") & filters.create(owner_filter))
    async def del_groups_init_handler(client, message):
        """FSM: инициализация массового удаления group_map"""
        PENDING_ACTIONS[message.from_user.id] = 'DEL_GROUPS'
        await message.reply_text(
            "Пришлите шаблоны для удаления (одно слово/фразу)\n" \
            "каждый с новой строки или через запятую."
        )

    @app.on_message(filters.text & filters.create(lambda _,__,msg: PENDING_ACTIONS.get(msg.from_user.id)=='DEL_GROUPS'))
    async def del_groups_fsm_handler(client, message):
        from src.group_map import remove_group_pattern
        patterns = [p.strip() for p in message.text.replace(',', '\n').splitlines() if p.strip()]
        removed, skipped = [], []
        for pat in patterns:
            if remove_group_pattern(pat):
                removed.append(pat)
            else:
                skipped.append(pat)
        reply = []
        if removed:
            reply.append(f"Удалены: {', '.join(removed)}")
        if skipped:
            reply.append(f"Не найдены: {', '.join(skipped)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не удалено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)
    
    @app.on_message(filters.command(["addspam"]) & filters.create(owner_filter))
    async def add_spam_self_handler(client, message):
        # Одиночное добавление спам-шаблона
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Укажите шаблон спама после команды.\nПример: /addspam .*spam.*")
            return
        pattern = parts[1].strip()
        if add_spam_pattern(pattern, SPAM_FILE):
            await message.reply_text(f"Шаблон спама '{pattern}' добавлен.")
        else:
            await message.reply_text("Такой шаблон уже есть или пустая строка.")

    @app.on_message(filters.command(["delspam"]) & filters.create(owner_filter))
    async def del_spam_self_handler(client, message):
        # Одиночное удаление спам-шаблона
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Укажите шаблон спама после команды.\nПример: /delspam .*spam.*")
            return
        pattern = parts[1].strip()
        if remove_spam_pattern(pattern, SPAM_FILE):
            await message.reply_text(f"Шаблон спама '{pattern}' удалён.")
        else:
            await message.reply_text("Шаблон не найден.")

    @app.on_message(filters.command(["addspams"]) & filters.create(owner_filter))
    async def add_spams_init_handler(client, message):
        # Инициализация FSM для добавления нескольких спам-шаблонов
        PENDING_ACTIONS[message.from_user.id] = 'ADD_SPAMS'
        await message.reply_text(
            "Пришлите шаблоны спама для добавления. Можно через запятую или каждую с новой строки."
        )

    @app.on_message(
        filters.text & filters.create(owner_filter) &
        filters.create(lambda _, __, m: PENDING_ACTIONS.get(m.from_user.id) == 'ADD_SPAMS')
    )
    async def add_spams_fsm_handler(client, message):
        # FSM: обработка добавления нескольких шаблонов спама
        patterns = message.text.replace(",", "\n").splitlines()
        added, skipped = [], []
        for p in patterns:
            p = p.strip()
            if not p:
                continue
            if add_spam_pattern(p, SPAM_FILE):
                added.append(p)
            else:
                skipped.append(p)
        reply = []
        if added:
            reply.append(f"Добавлены: {', '.join(added)}")
        if skipped:
            reply.append(f"Пропущены (уже есть/пусто): {', '.join(skipped)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не добавлено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)

    @app.on_message(filters.command(["delspams"]) & filters.create(owner_filter))
    async def del_spams_init_handler(client, message):
        # Инициализация FSM для удаления нескольких спам-шаблонов
        PENDING_ACTIONS[message.from_user.id] = 'DEL_SPAMS'
        await message.reply_text(
            "Пришлите шаблоны спама для удаления. Можно через запятую или каждую с новой строки."
        )

    @app.on_message(
        filters.text & filters.create(owner_filter) &
        filters.create(lambda _, __, m: PENDING_ACTIONS.get(m.from_user.id) == 'DEL_SPAMS')
    )
    async def del_spams_fsm_handler(client, message):
        # FSM: обработка удаления нескольких шаблонов спама
        patterns = message.text.replace(",", "\n").splitlines()
        removed, not_found = [], []
        for p in patterns:
            p = p.strip()
            if not p:
                continue
            if remove_spam_pattern(p, SPAM_FILE):
                removed.append(p)
            else:
                not_found.append(p)
        reply = []
        if removed:
            reply.append(f"Удалены: {', '.join(removed)}")
        if not_found:
            reply.append(f"Не найдены: {', '.join(not_found)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не удалено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)

    @app.on_message(filters.command(["addword", "addkey"]) & filters.create(owner_filter))
    async def add_word_self_handler(client, message):
        """
        Добавить ключевое слово через команду в избранных (или любом приватном чате от себя).
        Пример: /addword слово
        """
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Укажите ключевое слово после команды.\nПример: /addword интернет")
            return
        word = parts[1].strip()
        if add_keyword(word, KEYWORDS_FILE):
            await message.reply_text(f"Ключ '{word}' добавлен.")
        else:
            await message.reply_text("Такой ключ уже есть или пустая строка.")

    @app.on_message(filters.command(["delword", "delkey"]) & filters.create(owner_filter))
    async def del_word_self_handler(client, message):
        """
        Удалить ключевое слово через команду в избранных (или любом приватном чате от себя).
        Пример: /delword слово
        """
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("Укажите ключ для удаления.\nПример: /delword интернет")
            return
        word = parts[1].strip()
        if remove_keyword(word, KEYWORDS_FILE):
            await message.reply_text(f"Ключ '{word}' удалён.")
        else:
            await message.reply_text("Ключ не найден.")

    @app.on_message(filters.command(["showwords", "listkeys"]) & filters.create(owner_filter))
    async def show_words_self_handler(client, message):
        """
        Показать все ключевые слова.
        """
        keywords = load_keywords(KEYWORDS_FILE)
        if not keywords:
            await message.reply_text("Список ключей пуст.")
            return
        
        # Формируем красивый список с нумерацией
        text_lines = [f"{i+1}. {keyword}" for i, keyword in enumerate(keywords)]
        full_text = f"📝 Список ключевых слов ({len(keywords)} шт.):\n\n" + "\n".join(text_lines)
        
        # Если текст слишком длинный, разбиваем на части
        if len(full_text) > 4000:
            # Отправляем заголовок
            await message.reply_text(f"📝 Список ключевых слов ({len(keywords)} шт.):")
            
            # Разбиваем на части по 50 ключевых слов
            chunk_size = 50
            for i in range(0, len(keywords), chunk_size):
                chunk = keywords[i:i+chunk_size]
                chunk_lines = [f"{i+j+1}. {keyword}" for j, keyword in enumerate(chunk)]
                chunk_text = f"Часть {i//chunk_size + 1}:\n" + "\n".join(chunk_lines)
                await message.reply_text(chunk_text)
        else:
            await message.reply_text(full_text)

    @app.on_message(filters.command(["addwords", "addkeys"]) & filters.create(owner_filter))
    async def add_words_init_handler(client, message):
        """
        Инициализация добавления нескольких ключевых слов через FSM
        """
        PENDING_ACTIONS[message.from_user.id] = 'ADD_WORDS'
        await message.reply_text(
            "Пришлите ключевые слова для добавления. "
            "Можно через запятую или каждое с новой строки."
        )

    @app.on_message(
        filters.text & filters.create(owner_filter) &
        filters.create(lambda _, __, message: PENDING_ACTIONS.get(message.from_user.id) == 'ADD_WORDS')
    )
    async def add_words_fsm_handler(client, message):
        """
        FSM: обработка добавления нескольких слов
        """
        text = message.text
        words = text.replace(",", "\n").splitlines()
        added, skipped = [], []
        for w in words:
            w = w.strip()
            if not w:
                continue
            if add_keyword(w, KEYWORDS_FILE):
                added.append(w)
            else:
                skipped.append(w)
        reply = []
        if added:
            reply.append(f"Добавлены: {', '.join(added)}")
        if skipped:
            reply.append(f"Пропущены (уже есть/пусто): {', '.join(skipped)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не добавлено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)
        # далее сообщение не передаётся другим хэндлерам

    @app.on_message(filters.command(["delwords", "delkeys"]) & filters.create(owner_filter))
    async def del_words_init_handler(client, message):
        """
        Инициализация удаления нескольких ключевых слов через FSM
        """
        PENDING_ACTIONS[message.from_user.id] = 'DEL_WORDS'
        await message.reply_text(
            "Пришлите ключевые слова для удаления. "
            "Можно через запятую или каждое с новой строки."
        )

    @app.on_message(
        filters.text & filters.create(owner_filter) &
        filters.create(lambda _, __, msg: PENDING_ACTIONS.get(msg.from_user.id) == 'DEL_WORDS')
    )
    async def del_words_fsm_handler(client, message):
        # FSM: обработка удаления нескольких слов
        text = message.text
        words = text.replace(",", "\n").splitlines()
        removed, not_found = [], []
        for w in words:
            w = w.strip()
            if not w:
                continue
            if remove_keyword(w, KEYWORDS_FILE):
                removed.append(w)
            else:
                not_found.append(w)
        reply = []
        if removed:
            reply.append(f"Удалены: {', '.join(removed)}")
        if not_found:
            reply.append(f"Не найдены: {', '.join(not_found)}")
        await message.reply_text("\n".join(reply) if reply else "Ничего не удалено.")
        PENDING_ACTIONS.pop(message.from_user.id, None)
        # не продолжаем дальше до all_messages_handler

    @app.on_message(filters.command("help") & filters.create(owner_filter))
    async def help_self_handler(client, message):
        """
        Справка по командам userbot.
        """
        help_text = (
            "Userbot: управление ключевыми словами, спамом и семантическими группами через команды.\n\n"
            "📝 Управление ключевыми словами:\n"
            "/addword <слово> — добавить одно ключевое слово\n"
            "/delword <слово> — удалить одно ключевое слово\n"
            "/addwords — начать добавление нескольких ключевых слов\n"
            "    (после команды пришлите список через запятую или с новой строки)\n"
            "/delwords — начать удаление нескольких ключевых слов\n"
            "    (после команды пришлите список через запятую или с новой строки)\n"
            "/showwords — показать все ключевые слова\n\n"
            "🚫 Управление спам-шаблонами:\n"
            "/addspam <шаблон> — добавить шаблон спама\n"
            "/delspam <шаблон> — удалить шаблон спама\n"
            "/addspams — начать добавление нескольких шаблонов спама\n"
            "    (после команды пришлите список через запятую или с новой строки)\n"
            "/delspams — начать удаление нескольких шаблонов спама\n"
            "    (после команды пришлите список через запятую или с новой строки)\n"
            "/showspam — показать все шаблоны спама\n\n"
            "🔧 Управление семантическими группами:\n"
            "/showgroups — показать все семантические шаблоны и их группы\n"
            "/addgroup <паттерн>|<группа> — добавить шаблон в группу\n"
            "/delgroup <паттерн> — удалить шаблон из группы\n"
            "/addgroups — массовое добавление шаблонов в группу (FSM)\n"
            "/delgroups — массовое удаление шаблонов из группы (FSM)\n"
            "(узнать текущее количество групп: /showgroups)\n\n"
            "📊 Мониторинг качества:\n"
            "/stats — показать статистику качества совпадений\n"
            "/clear_stats — очистить статистику\n\n"
            "/help — эта справка\n\n"
            "ℹ️ Описание фильтров:\n"
            "- Спам-фильтр: regex из spam_patterns.txt\n"
            "- Прямой match: минимум 2 ключевых слова и хотя бы одна группа 'network'\n"
            "- Semantic shortcut: группы 'network'+'connect' или 'network'+'complaint'\n"
            "- Semantic proximity: минимум 2 группы и ≤10 токенов между найденными леммами\n"
            "\n"
        )
        await message.reply_text(help_text)

    @app.on_message(filters.command(["stats", "quality"]) & filters.private & filters.me)
    async def stats_handler(client, message):
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
                        await message.reply_text(f"📊 Статистика качества (часть {i+1}/{len(parts)}):\n\n{part}")
                    else:
                        await message.reply_text(f"📊 Статистика качества (часть {i+1}/{len(parts)}):\n\n{part}")
            else:
                await message.reply_text(f"📊 Статистика качества:\n\n{report}")
                
        except Exception as e:
            await message.reply_text(f"Ошибка при генерации статистики: {str(e)}")

    @app.on_message(filters.command("clear_stats") & filters.private & filters.me)
    async def clear_stats_handler(client, message):
        """
        Очистить статистику качества
        """
        import os
        
        log_file = "match_quality.log"
        if os.path.exists(log_file):
            os.remove(log_file)
            await message.reply_text("📊 Статистика качества очищена.")
        else:
            await message.reply_text("📊 Файл статистики не найден.")

    @app.on_message(filters.text)
    async def all_messages_handler(client, message):
        logger.debug(f"all_messages_handler: chat_id={message.chat.id}, chat_type={message.chat.type}, user_id={getattr(message.from_user, 'id', None)}, text={message.text[:50] if message.text else ''}")
        try:
            text = message.text or ""
            # Используем простую функцию поиска
            matches = simple_keyword_match(text)
            if matches:
                matches_str = ', '.join(matches)
                logger.info(f"Совпадение ключей: {matches_str} в чате {message.chat.id} ({message.chat.type})")
                notify_text = (
                    f"🔔 Совпадение по ключам: {matches_str}\n"
                    f"Чат: {message.chat.title or message.chat.id} ({message.chat.type})\n"
                    f"Пользователь: {message.from_user.first_name if message.from_user else 'N/A'}\n"
                    f"Текст:\n{text[:500]}"
                )
                if str(message.chat.id).startswith("-100") and hasattr(message, "id"):
                    chat_id_num = str(message.chat.id)[4:]
                    notify_text += f"\n[Открыть сообщение](https://t.me/c/{chat_id_num}/{message.id})"
                await client.send_message("me", notify_text, disable_web_page_preview=True)
                try:
                    await client.forward_messages("me", message.chat.id, message.id)
                    logger.debug(f"Переслано сообщение {message.id} из чата {message.chat.id} в избранное.")
                except ValueError as e:
                    if "Peer id invalid" in str(e):
                        logger.warning(f"Ошибка пересылки: Peer id invalid ({message.chat.id}). Скорее всего, userbot не состоит в этом чате или Pyrogram не видит его в сессии. Пересылка невозможна. Подробнее: {e}")
                    else:
                        logger.warning(f"Ошибка пересылки сообщения: {e}")
                except Exception as e:
                    logger.warning(f"Неизвестная ошибка пересылки сообщения: {e}")
        except Exception as e:
            logger.error(f"Ошибка в обработчике сообщений: {e}")

    # --- Закомментированные старые функции поиска ---
    # def smart_find_match(text, keywords, context="", threshold=85):
    #     ...
    # def _validate_match(norm_text, matched_norm, full_context):
    #     ...
    # def _is_contextually_relevant(text):
    #     ...
    # def analyze_match_quality(text, matched_keyword):
    #     ...
