import spacy
from rapidfuzz import fuzz
import re
from src.keywords import load_keywords  # функция для загрузки списка слов
from loguru import logger  # Добавлено логирование
from src.config import KEYWORDS_FILE  # используем конфиг для пути к файлу

# Загружаем модель для русского языка
nlp = spacy.load("ru_core_news_sm")


def simple_keyword_match(text: str, fuzz_threshold: int = 90) -> list[str] | None:
    """
    Поиск ключевого слова с использованием spaCy:
    1) Multi-word: ищет точную последовательность лемм
    2) Single-word: точное совпадение леммы или fuzzy-сравнение лемм
    """
    text = str(text)
    # Загрузка и подготовка ключей внутри функции
    raw_keywords = load_keywords(KEYWORDS_FILE)
    kw_single: dict[str, str] = {}
    kw_multi: list[tuple[tuple[str,...], str]] = []
    for kw in raw_keywords:
        doc_kw = nlp(kw)
        lem_list = tuple(token.lemma_.lower() for token in doc_kw if token.is_alpha)
        if not lem_list:
            continue
        if len(lem_list) == 1:
            kw_single.setdefault(lem_list[0], kw)
        else:
            kw_multi.append((lem_list, kw))

    doc = nlp(text)
    lemmas = [token.lemma_.lower() for token in doc if token.is_alpha]

    logger.debug(f"simple_keyword_match: lemmas={lemmas}, fuzz_threshold={fuzz_threshold}")

    # Собираем все найденные ключевые слова
    matches: set[str] = set()

    # 1) Multi-word
    for kw_lem, original in kw_multi:
        if len(kw_lem) > len(lemmas):
            continue
        for i in range(len(lemmas) - len(kw_lem) + 1):
            window = tuple(lemmas[i : i + len(kw_lem)])
            if window == kw_lem:
                logger.info(f"Found multi-word keyword '{original}' in window {window}")
                matches.add(original)

    # 2) Single-word exact
    for lemma in lemmas:
        if lemma in kw_single:
            original = kw_single[lemma]
            logger.info(f"Found single-word keyword '{original}' exact match for lemma '{lemma}'")
            matches.add(original)

    # 3) Single-word fuzzy
    for lemma in lemmas:
        for key_lem, original in kw_single.items():
            ratio = fuzz.ratio(lemma, key_lem)
            if ratio >= fuzz_threshold:
                logger.info(f"Found fuzzy match keyword '{original}' for lemma '{lemma}' vs key_lemma '{key_lem}', ratio={ratio}")
                matches.add(original)

    # Проверяем количество найденных ключевых слов
    if len(matches) >= 2:
        logger.info(f"Total keywords matched: {len(matches)} -> {matches}")
        return list(matches)
    logger.debug(f"Недостаточно совпадений ключевых слов ({len(matches)}): {matches}")
    return None
