import re
from rapidfuzz import fuzz
import spacy
from loguru import logger
from src.keywords import load_keywords, load_spam_patterns
from src.config import KEYWORDS_FILE, SPAM_FILE

# Загрузка модели spaCy один раз
nlp = spacy.load("ru_core_news_sm")

# Семантические группы для ключей; заполните по своему словарю
RAW_GROUP_MAP = {
    # === NETWORK ===
    "интернет":         "network",
    "сеть":             "network",
    "сетевой":          "network",
    "вайфай":           "network",
    "wi-fi":            "network",
    "вай-фай":          "network",
    "роутер":           "network",
    "модем":            "network",
    "кабель":           "network",
    "пинг":             "network",
    "dns":              "network",
    "ip":               "network",
    "подключение":      "network",
    "локалка":          "network",
    "инет":             "network",
    "доступ":           "network",

    # === OPERATOR NAMES ===
    "ростелеком":       "operator",
    "ртком":            "operator",
    "домру":            "operator",
    "дом.ру":           "operator",
    "билайн":           "operator",
    "мтс":              "operator",
    "мегафон":          "operator",
    "ттк":              "operator",
    "юг-линк":          "operator",
    "йота":             "operator",
    "инфолинк":         "operator",
    "интерсвязь":       "operator",
    "обит":             "operator",

    # === CONNECTION REQUESTS ===
    "хочу подключить":          "connect",
    "как подключиться":         "connect",
    "заявка на подключение":    "connect",
    "оформить подключение":     "connect",
    "оформление подключения":   "connect",
    "можно подключиться":       "connect",
    "где подключить":           "connect",
    "куда обращаться":          "connect",
    "оставить заявку":          "connect",
    "подключить":               "connect",
    "подключиться":             "connect",
    "подключаюсь":              "connect",
    "подключаю":                "connect",
    "подключка":                "connect",
    "сменить провайдера":       "connect",
    "сменить оператора":        "connect",
    "ищу альтернативу":         "connect",
    "перейти на":               "connect",
    "альтернатива":             "connect",
    "сравниваю":                "connect",
    "ищу провайдера":           "connect",
    "что подключить":           "connect",
    "переезжаю":                "connect",

    # === COMPLAINTS ===
    "плохой интернет":          "complaint",
    "интернет не работает":    "complaint",
    "нет интернета":            "complaint",
    "инет лагает":              "complaint",
    "падает интернет":          "complaint",
    "низкая скорость":          "complaint",
    "медленно работает":        "complaint",
    "частые обрывы":            "complaint",
    "пропадает связь":          "complaint",
    "постоянные лаги":          "complaint",
    "обрывы":                   "complaint",
    "сбой сети":                "complaint",
    "нет сигнала":              "complaint",
    "не грузит":                "complaint",
    "вообще не работает":       "complaint",
    "зависает":                 "complaint",
    "перезагружаю каждый день": "complaint",

    # === OTHER SUPPORT/FORMAL ===
    "заявка":                   "connect",
    "адрес":                    "connect",
    "оставил заявку":           "connect",
    "заявление":                "connect",
    "оформление":               "connect",
    "договор":                  "connect",
    "поддержка":               "connect",
    "техподдержка":            "connect",
}

def normalize_group_map(raw_map: dict[str, str]) -> dict[str, str]:
    norm_map = {}
    for word, group in raw_map.items():
        doc = nlp(word)
        for token in doc:
            if token.is_alpha:
                norm_map[token.lemma_.lower()] = group
    return norm_map

GROUP_MAP = normalize_group_map(RAW_GROUP_MAP)  # RAW_GROUP_MAP — словарь с формами слов

# Загружаем и компилируем шаблоны спама из keywords.py
SPAM_PATTERNS = load_spam_patterns(SPAM_FILE)
SPAM_REGEX = [re.compile(p, flags=re.IGNORECASE) for p in SPAM_PATTERNS]


# Пороговые параметры
FUZZ_THRESH     = 85   # процент для fuzzy
MIN_MATCHES     = 1    # требуем минимум 1 совпадение ключа
# требуем минимум 2 семантических групп при групповом фильтре
MIN_GROUPS      = 2    # из минимум 2 семантических групп
MAX_TOKEN_DIST  = 10   # расстояние между ключевыми леммами


def simple_keyword_match(text: str) -> list[str] | None:
    """
    Фильтр релевантных сообщений для провайдера:
      – Отсекает спам-объявления по телефонам/ссылкам
      – Лемматизирует текст через spaCy
      – Находит multi-word и single-word ключи (exact & fuzzy)
      – Требует минимум 2 совпадения из разных групп
      – Гарантирует, что совпадения близко по контексту (≤ MAX_TOKEN_DIST токенов)
    
    Возвращает список найденных оригинальных ключей или None.
    """
    text = str(text)
    t_lower = text.lower()

    # 0) Спам-фильтр
    # Проверяем спам с помощью скомпилированных regex
    for spam_re in SPAM_REGEX:
        if spam_re.search(t_lower):
            logger.debug(f"Отфильтровано как спам по шаблону: {spam_re.pattern}")
            return None
        
    # 1) Подготовка ключей
    raw_keywords = load_keywords(KEYWORDS_FILE)
    kw_single = {}   # лемма → оригинал
    kw_multi  = []   # [(tuple(лемм...), оригинал), ...]

    for kw in raw_keywords:
        lemmas = tuple(token.lemma_.lower() for token in nlp(kw) if token.is_alpha)
        if not lemmas:
            continue
        if len(lemmas) == 1:
            kw_single.setdefault(lemmas[0], kw)
        else:
            kw_multi.append((lemmas, kw))

    # 2) Лемматизация текста
    doc    = nlp(text)
    lemmas = [token.lemma_.lower() for token in doc if token.is_alpha]
    
    # Сопоставляем группы по леммам (и фразам из лемм)
    matched_groups = set()
    text_lemmas_str = " ".join(lemmas)
    for pattern, group in GROUP_MAP.items():
        if pattern in text_lemmas_str:
            matched_groups.add(group)
            
    matches      = set()
    groups_found = set()
    positions    = []

    # 3) Multi-word match
    for kw_lem, original in kw_multi:
        L = len(kw_lem)
        if L > len(lemmas):
            continue
        for i in range(len(lemmas) - L + 1):
            window = tuple(lemmas[i: i + L])
            if window == kw_lem:
                matches.add(original)
                grp = GROUP_MAP.get(original, "other")
                groups_found.add(grp)
                positions.append(i)
                logger.info(f"Multi-word match '{original}' at pos {i}")
                break

    # 4) Single-word exact match
    for idx, lemma in enumerate(lemmas):
        if lemma in kw_single:
            original = kw_single[lemma]
            matches.add(original)
            grp = GROUP_MAP.get(original, "other")
            groups_found.add(grp)
            positions.append(idx)
            logger.info(f"Single exact match '{original}' at pos {idx}")

    # 5) Single-word fuzzy match (требуем хотя бы два таких совпадения)
    fuzzy_hits = 0
    for idx, lemma in enumerate(lemmas):
        for key_lem, original in kw_single.items():
            ratio = fuzz.ratio(lemma, key_lem)
            if ratio >= FUZZ_THRESH:
                fuzzy_hits += 1
                if fuzzy_hits > 1:
                    matches.add(original)
                    grp = GROUP_MAP.get(original, "other")
                    groups_found.add(grp)
                    positions.append(idx)
                    logger.info(
                        f"Fuzzy match '{original}' for lemma='{lemma}' "
                        f"vs key='{key_lem}', ratio={ratio} at pos {idx}"
                    )
                break

    # 6) Финальный фильтр
    # Итоговый фильтр: два пути к принятию сообщения
    # 1) Достаточно прямых совпадений ключевых слов
    if len(matches) >= MIN_MATCHES:
        logger.info(f"Прямые совпадения: matches={matches}")
        return list(matches)
    # 2) Достаточно семантических групп и близость по позиции
    if len(matched_groups) >= MIN_GROUPS and len(groups_found) >= MIN_GROUPS \
       and positions and (max(positions) - min(positions) <= MAX_TOKEN_DIST):
        logger.info(
            f"Семантический фильтр: matched_groups={matched_groups}, "
            f"groups_found={groups_found}, positions={positions}"
        )
        return list(matches)
    # В остальных случаях отклоняем
    logger.debug(f"Отклонено: matches={matches}, matched_groups={matched_groups}, groups_found={groups_found}, positions={positions}")
    
    # (перед последним return None)
    #  — если в тексте одновременно найдены две группы: сеть и запрос на подключение/жалобу,
    #    но не было точных matches, принимаем.
    if {"network", "connect"} <= matched_groups or {"network", "complaint"} <= matched_groups:
        logger.info(f"Semantic shortcut: {matched_groups} → accept")
        return []  # или верните нужные ключи, например ["интернет","подключить"]
        
        
    return None