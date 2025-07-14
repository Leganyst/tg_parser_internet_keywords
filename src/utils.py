import re
from rapidfuzz import fuzz
import spacy
from loguru import logger
from src.keywords import load_keywords, load_spam_patterns
from src.config import KEYWORDS_FILE, SPAM_FILE

# Загрузка модели spaCy один раз
nlp = spacy.load("ru_core_news_sm")

# Загружаем маппинг групп из JSON-конфига
import json
from pathlib import Path

_config_path = Path(__file__).parent / "group_map.json"
with open(_config_path, encoding="utf-8") as f:
    _raw_map: dict[str, str] = json.load(f)

# Разделяем на однословные паттерны и многословные
SINGLE_GROUP_MAP: dict[str, str] = {}
MULTI_GROUP_PATTERNS: list[tuple[tuple[str], str]] = []
for pattern, group in _raw_map.items():
    doc = nlp(pattern)
    lemmas_pat = tuple(token.lemma_.lower() for token in doc if token.is_alpha)
    if len(lemmas_pat) == 1:
        SINGLE_GROUP_MAP[lemmas_pat[0]] = group
    elif len(lemmas_pat) > 1:
        MULTI_GROUP_PATTERNS.append((lemmas_pat, group))

# Обратно совместимый GROUP_MAP: строковый паттерн → группа
GROUP_MAP: dict[str, str] = {}
for lemma, grp in SINGLE_GROUP_MAP.items():
    GROUP_MAP[lemma] = grp
for lem_pat, grp in MULTI_GROUP_PATTERNS:
    GROUP_MAP[" ".join(lem_pat)] = grp

# Загружаем и компилируем шаблоны спама из keywords.py
SPAM_PATTERNS = load_spam_patterns(SPAM_FILE)
SPAM_REGEX = [re.compile(p, flags=re.IGNORECASE) for p in SPAM_PATTERNS]


# Пороговые параметры
FUZZ_THRESH     = 85   # процент для fuzzy
MIN_MATCHES     = 2    # требуем минимум 2 совпадения ключей для прямого прохода
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
    
    # Сопоставляем семантические группы: сначала многословные, затем одиночные
    matched_groups = set()
    # многословные группы
    for lem_pat, group in MULTI_GROUP_PATTERNS:
        L = len(lem_pat)
        if L > len(lemmas):
            continue
        for i in range(len(lemmas) - L + 1):
            if tuple(lemmas[i: i + L]) == lem_pat:
                matched_groups.add(group)
                break
    # одиночные группы
    for lemma in lemmas:
        grp = SINGLE_GROUP_MAP.get(lemma)
        if grp:
            matched_groups.add(grp)
            
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
                # Группа найденного ключевого шаблона по JSON-мапе
                grp = _raw_map.get(original, "other")
                groups_found.add(grp)
                positions.append(i)
                logger.info(f"Multi-word match '{original}' at pos {i}")
                break

    # 4) Single-word exact match
    for idx, lemma in enumerate(lemmas):
        if lemma in kw_single:
            original = kw_single[lemma]
            matches.add(original)
            # Группа для одиночного слова
            grp = _raw_map.get(original, "other")
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
                    # Группа для fuzzy-совпадения
                    grp = _raw_map.get(original, "other")
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
    if len(matches) >= MIN_MATCHES and 'network' in groups_found:
        logger.info(f"Direct accept: matches={matches}, groups_found={groups_found}")
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
        return list(matched_groups)

    # Без совпадений групп и ключей отклоняем
    return None