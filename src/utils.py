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
MIN_MATCHES     = 1    # требуем минимум 2 совпадения ключей для прямого прохода
# требуем минимум 2 семантических групп при групповом фильтре
MIN_GROUPS      = 2    # из минимум 2 семантических групп
MAX_TOKEN_DIST  = 10   # расстояние между ключевыми леммами


def simple_keyword_match(text: str) -> list[str] | None:
    """
    Фильтр релевантных сообщений для провайдера:
      – Спам-фильтр
      – Лемматизация через spaCy
      – Multi-word и single-word exact & fuzzy match
      – Relaxed direct accept по одному ключу + семантика «network»
      – Семантический фильтр по группам и расстоянию
      – Ранний semantic shortcut «network + connect/complaint»
    """
    text = str(text)
    t_lower = text.lower()

    # 0) Спам-фильтр
    for spam_re in SPAM_REGEX:
        if spam_re.search(t_lower):
            logger.debug(f"Отфильтровано как спам: {spam_re.pattern}")
            return None

    # 1) Загружаем ключи
    raw_keywords = load_keywords(KEYWORDS_FILE)
    kw_single, kw_multi = {}, []
    for kw in raw_keywords:
        lemmas = tuple(tok.lemma_.lower() for tok in nlp(kw) if tok.is_alpha)
        if len(lemmas) == 1:
            kw_single.setdefault(lemmas[0], kw)
        elif lemmas:
            kw_multi.append((lemmas, kw))

    # 2) Лемматизируем вход
    doc    = nlp(text)
    lemmas = [tok.lemma_.lower() for tok in doc if tok.is_alpha]

    # 3) Собираем matched_groups
    matched_groups = set()
    #   3a) multi-word группы
    for pat, grp in MULTI_GROUP_PATTERNS:
        L = len(pat)
        for i in range(len(lemmas) - L + 1):
            if tuple(lemmas[i : i + L]) == pat:
                matched_groups.add(grp)
                break
    #   3b) single-word группы
    for lm in lemmas:
        if lm in SINGLE_GROUP_MAP:
            matched_groups.add(SINGLE_GROUP_MAP[lm])

    matches, groups_found, positions = set(), set(), []

    # 4) Multi-word exact match
    for kw_pat, orig in kw_multi:
        L = len(kw_pat)
        for i in range(len(lemmas) - L + 1):
            if tuple(lemmas[i : i + L]) == kw_pat:
                matches.add(orig)
                groups_found.add(_raw_map.get(orig, "other"))
                positions.append(i)
                break

    # 5) Single-word exact match
    for idx, lm in enumerate(lemmas):
        if lm in kw_single:
            orig = kw_single[lm]
            matches.add(orig)
            groups_found.add(_raw_map.get(orig, "other"))
            positions.append(idx)

    # 6) Single-word fuzzy match
    for idx, lm in enumerate(lemmas):
        for key_lem, orig in kw_single.items():
            if fuzz.ratio(lm, key_lem) >= FUZZ_THRESH:
                # сразу принимаем один сильный fuzzy-match
                matches.add(orig)
                groups_found.add(_raw_map.get(orig, "other"))
                positions.append(idx)
                break

    # DEBUG после матчей
    logger.debug(f"After matching: matches={matches}, "
                 f"matched_groups={matched_groups}, "
                 f"groups_found={groups_found}, positions={positions}")

    # 7) Relaxed direct accept:
    #    достаточно одного match + упоминание «network» в семантике
    if matches and 'network' in matched_groups:
        logger.info(f"Direct accept (relaxed): {matches}")
        return list(matches)

    # 8) Семантический фильтр по группам + позиции
    if (len(matched_groups) >= MIN_GROUPS and
        len(groups_found) >= MIN_GROUPS and
        positions and
        max(positions) - min(positions) <= MAX_TOKEN_DIST):
        logger.info("Semantic positional accept")
        return list(matches)

    # 9) Semantic shortcut (ранний):
    #    если есть одновременно network+connect или network+complaint
    if ({'network','connect'}.issubset(matched_groups) or
        {'network','complaint'}.issubset(matched_groups)):
        logger.info(f"Semantic shortcut applied: {matched_groups}")
        return list(matched_groups)

    # 10) Отклоняем
    logger.debug("Rejected")
    return None
