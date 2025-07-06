import re
from .keywords import load_keywords
from rapidfuzz import fuzz, process
from .morphology_config import (
    FALSE_POSITIVE_WORDS, RELEVANCE_INDICATORS, 
    SIMILARITY_THRESHOLDS, MIN_LENGTH_RATIO, SCORING_MODIFIERS
)

def find_match(text, keywords, threshold=85, use_regex=True, ignore_case=True):
    """
    Улучшенный поиск совпадений с морфологическим анализом
    """
    # Нормализация текста
    norm_text = text.lower().strip().replace('\n', ' ').replace('\r', ' ')
    
    # Удаляем лишние пробелы
    norm_text = re.sub(r'\s+', ' ', norm_text)
    
    # Если текст слишком короткий (меньше 3 символов), повышаем требования
    min_length_for_short = 3
    if len(norm_text) < min_length_for_short:
        # Для коротких слов требуем точное совпадение или очень высокое сходство
        return find_exact_or_high_similarity(norm_text, keywords, 95)
    
    # 1. Сначала пробуем точное совпадение
    exact_match = find_exact_match(norm_text, keywords)
    if exact_match:
        return exact_match
    
    # 2. Затем пробуем regex с границами слов
    if use_regex:
        regex_match = find_regex_match(norm_text, keywords, ignore_case)
        if regex_match:
            return regex_match
    
    # 3. Fuzzy matching с улучшенной логикой
    fuzzy_match = find_fuzzy_match(norm_text, keywords, threshold)
    return fuzzy_match

def find_exact_match(norm_text, keywords):
    """Поиск точного совпадения"""
    for kw in keywords:
        kw_norm = kw.lower().strip()
        if kw_norm == norm_text:
            return kw
        # Проверяем вхождение как отдельного слова
        if f" {kw_norm} " in f" {norm_text} ":
            return kw
    return None

def find_regex_match(norm_text, keywords, ignore_case):
    """Улучшенный regex поиск с границами слов"""
    # Сортируем ключевые слова по длине (сначала длинные)
    sorted_keywords = sorted([kw for kw in keywords if kw.strip()], key=len, reverse=True)
    
    for kw in sorted_keywords:
        kw_cleaned = kw.strip()
        if not kw_cleaned:
            continue
            
        # Специальная обработка для доменов и названий компаний
        if '.' in kw_cleaned or 'ру' in kw_cleaned.lower():
            pattern = rf"\b{re.escape(kw_cleaned)}\b"
        else:
            # Для обычных слов используем более строгие границы
            pattern = rf"(?:^|\s){re.escape(kw_cleaned)}(?:\s|$)"
        
        flags = re.IGNORECASE if ignore_case else 0
        if re.search(pattern, norm_text, flags):
            return kw_cleaned
    
    return None

def find_fuzzy_match(norm_text, keywords, threshold):
    """Улучшенный fuzzy поиск"""
    best_match = None
    best_ratio = 0
    
    for kw in keywords:
        kw_norm = kw.lower().strip()
        if not kw_norm:
            continue
        
        # Вычисляем различные типы сходства
        token_ratio = fuzz.token_sort_ratio(norm_text, kw_norm)
        partial_ratio = fuzz.partial_ratio(norm_text, kw_norm)
        ratio = fuzz.ratio(norm_text, kw_norm)
        
        # Для коротких ключевых слов требуем более высокое сходство
        if len(kw_norm) <= 5:
            required_threshold = threshold + 10
        else:
            required_threshold = threshold
        
        # Используем максимальное значение из всех типов сходства
        max_ratio = max(token_ratio, partial_ratio, ratio)
        
        # Дополнительная проверка: если слово очень короткое, 
        # но есть частичное совпадение - снижаем порог
        if len(norm_text) <= 3 and len(kw_norm) > 10:
            if partial_ratio >= 70 and norm_text in kw_norm:
                max_ratio = max_ratio * 1.1  # Небольшой бонус
        
        if max_ratio >= required_threshold and max_ratio > best_ratio:
            best_ratio = max_ratio
            best_match = kw
    
    return best_match

def find_exact_or_high_similarity(norm_text, keywords, high_threshold):
    """Поиск для очень коротких текстов"""
    for kw in keywords:
        kw_norm = kw.lower().strip()
        if kw_norm == norm_text:
            return kw
        
        # Для очень коротких слов требуем практически точное совпадение
        ratio = fuzz.ratio(norm_text, kw_norm)
        if ratio >= high_threshold:
            return kw
    
    return None

def validate_match(text, matched_keyword, keywords):
    """
    Дополнительная валидация найденного совпадения
    Помогает отфильтровать ложные срабатывания
    """
    if not matched_keyword:
        return False
    
    norm_text = text.lower().strip()
    matched_norm = matched_keyword.lower().strip()
    
    # Если найденное слово в списке исключений и оно короткое
    if norm_text in FALSE_POSITIVE_WORDS and len(norm_text) <= 5:
        # Проверяем, действительно ли это релевантное совпадение
        if not is_contextually_relevant(norm_text, matched_norm):
            return False
    
    # Проверяем минимальную длину для коротких совпадений
    if len(norm_text) <= 3 and len(matched_norm) > 10:
        # Для очень коротких слов требуем, чтобы они были частью составного ключевого слова
        if norm_text not in matched_norm:
            return False
    
    # Проверяем соотношение длин
    length_ratio = min(len(norm_text), len(matched_norm)) / max(len(norm_text), len(matched_norm))
    if length_ratio < MIN_LENGTH_RATIO:
        # Требуем более строгой проверки
        similarity = fuzz.ratio(norm_text, matched_norm)
        if similarity < SIMILARITY_THRESHOLDS['high_confidence']:
            return False
    
    return True

def is_contextually_relevant(text, keyword):
    """
    Проверяет контекстуальную релевантность совпадения
    """
    combined_text = f"{text} {keyword}".lower()
    
    for pattern in RELEVANCE_INDICATORS:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return True
    
    return False

def enhanced_find_match(text, keywords, threshold=85):
    """
    Улучшенная функция поиска с дополнительной валидацией
    """
    # Сначала находим потенциальное совпадение
    potential_match = find_match(text, keywords, threshold)
    
    # Затем валидируем его
    if validate_match(text, potential_match, keywords):
        return potential_match
    
    return None

def analyze_match_quality(text, matched_keyword):
    """
    Анализирует качество найденного совпадения и возвращает метрики
    """
    if not matched_keyword:
        return None
    
    norm_text = text.lower().strip()
    matched_norm = matched_keyword.lower().strip()
    
    # Различные метрики сходства
    exact_ratio = fuzz.ratio(norm_text, matched_norm)
    partial_ratio = fuzz.partial_ratio(norm_text, matched_norm)
    token_ratio = fuzz.token_sort_ratio(norm_text, matched_norm)
    
    # Анализ длины
    length_ratio = min(len(norm_text), len(matched_norm)) / max(len(norm_text), len(matched_norm))
    
    # Контекстуальная релевантность
    is_relevant = is_contextually_relevant(norm_text, matched_norm)
    
    return {
        'exact_similarity': exact_ratio,
        'partial_similarity': partial_ratio,
        'token_similarity': token_ratio,
        'length_ratio': length_ratio,
        'is_contextually_relevant': is_relevant,
        'quality_score': (exact_ratio + partial_ratio + token_ratio) / 3,
        'confidence': 'high' if exact_ratio > 85 else 'medium' if exact_ratio > 70 else 'low'
    }

def get_top_matches(text, keywords, top_n=3):
    """
    Возвращает топ-N лучших совпадений с метриками качества
    """
    matches = []
    norm_text = text.lower().strip()
    
    for keyword in keywords:
        keyword_norm = keyword.lower().strip()
        if not keyword_norm:
            continue
            
        # Вычисляем все метрики
        exact_ratio = fuzz.ratio(norm_text, keyword_norm)
        partial_ratio = fuzz.partial_ratio(norm_text, keyword_norm)
        token_ratio = fuzz.token_sort_ratio(norm_text, keyword_norm)
        
        overall_score = max(exact_ratio, partial_ratio, token_ratio)
        
        if overall_score > 50:  # Минимальный порог для рассмотрения
            quality = analyze_match_quality(text, keyword)
            matches.append({
                'keyword': keyword,
                'score': overall_score,
                'quality': quality
            })
    
    # Сортируем по качеству и возвращаем топ-N
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:top_n]

def smart_find_match(text, keywords, context="", threshold=85):
    """
    Интеллектуальный поиск с учетом контекста и улучшенной логикой
    
    Args:
        text: Анализируемый текст
        keywords: Список ключевых слов
        context: Дополнительный контекст (например, предыдущие сообщения)
        threshold: Порог сходства
    """
    # Нормализация
    norm_text = text.lower().strip().replace('\n', ' ')
    norm_text = re.sub(r'\s+', ' ', norm_text)
    
    # Объединяем текст с контекстом
    full_context = f"{context} {norm_text}".strip()
    
    # 1. Проверяем явные упоминания провайдеров/интернета
    explicit_match = find_explicit_internet_mention(full_context, keywords)
    if explicit_match:
        return explicit_match
    
    # 2. Для очень коротких текстов - особая логика
    if len(norm_text) <= 3:
        return handle_short_text(norm_text, keywords, full_context)
    
    # 3. Стандартный улучшенный поиск
    return enhanced_find_match(text, keywords, threshold)

def find_explicit_internet_mention(text, keywords):
    """Поиск явных упоминаний интернета или провайдеров"""
    text_lower = text.lower()
    
    # Приоритетные паттерны
    priority_patterns = [
        r'\b(интернет|инет)\s+(не\s+работает|пропал|отключили|лагает|тормозит)\b',
        r'\b(ростелеком|дом\.ру|домру|билайн|мтс|мегафон|ттк)\s+\w+',
        r'\b(плохой|низкая|высокий)\s+(интернет|пинг|скорость)\b',
        r'\b(проблемы|лаги|обрывы)\s+(с|интернет|связь)\b'
    ]
    
    for pattern in priority_patterns:
        match = re.search(pattern, text_lower)
        if match:
            # Ищем наиболее подходящее ключевое слово
            matched_text = match.group(0)
            for keyword in keywords:
                if any(word in keyword.lower() for word in matched_text.split()):
                    return keyword
    
    return None

def handle_short_text(short_text, keywords, full_context):
    """Специальная обработка коротких текстов"""
    
    # Для коротких слов проверяем контекст
    if is_contextually_relevant(full_context, ""):
        # Ищем точные совпадения в контексте интернета
        for keyword in keywords:
            if short_text in keyword.lower():
                # Дополнительная проверка - является ли это осмысленным совпадением
                if len(keyword) <= len(short_text) * 3:  # Не слишком длинное ключевое слово
                    return keyword
    
    return None

def calculate_smart_similarity(text1, text2, context=""):
    """Умный расчет сходства с учетом контекста"""
    base_similarity = fuzz.ratio(text1.lower(), text2.lower())
    
    # Модификаторы
    modifiers = 0
    
    # Бонус за контекстуальную релевантность
    if is_contextually_relevant(f"{context} {text1} {text2}", ""):
        modifiers += SCORING_MODIFIERS['contextual_bonus']
    
    # Штраф за разную длину
    length_ratio = min(len(text1), len(text2)) / max(len(text1), len(text2))
    if length_ratio < MIN_LENGTH_RATIO:
        modifiers += SCORING_MODIFIERS['length_penalty']
    
    # Штраф за очень короткие слова без контекста
    if len(text1) <= 3 and not context:
        modifiers += SCORING_MODIFIERS['short_word_penalty']
    
    # Бонус за точное вхождение
    if text1.lower() in text2.lower() or text2.lower() in text1.lower():
        modifiers += SCORING_MODIFIERS['exact_match_bonus']
    
    return min(100, max(0, base_similarity + modifiers))
