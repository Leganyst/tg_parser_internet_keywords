import re
from .keywords import load_keywords
from rapidfuzz import fuzz
from .morphology_config import (
    FALSE_POSITIVE_WORDS, RELEVANCE_INDICATORS, 
    SIMILARITY_THRESHOLDS, MIN_LENGTH_RATIO
)

def smart_find_match(text, keywords, context="", threshold=85):
    """
    Единственная функция поиска с морфологическим анализом и контекстом
    """
    # Нормализация
    norm_text = text.lower().strip().replace('\n', ' ')
    norm_text = re.sub(r'\s+', ' ', norm_text)
    
    # Объединяем текст с контекстом
    full_context = f"{context} {norm_text}".strip()
    
    # 1. Проверяем точное совпадение
    for kw in keywords:
        kw_norm = kw.lower().strip()
        if kw_norm == norm_text or f" {kw_norm} " in f" {norm_text} ":
            return kw
    
    # 2. Проверяем regex с границами слов (сортируем по длине)
    sorted_keywords = sorted([kw for kw in keywords if kw.strip()], key=len, reverse=True)
    for kw in sorted_keywords:
        kw_cleaned = kw.strip()
        if not kw_cleaned:
            continue
            
        # Специальная обработка для доменов
        if '.' in kw_cleaned or 'ру' in kw_cleaned.lower():
            pattern = rf"\b{re.escape(kw_cleaned)}\b"
        else:
            pattern = rf"(?:^|\s){re.escape(kw_cleaned)}(?:\s|$)"
        
        if re.search(pattern, norm_text, re.IGNORECASE):
            return kw_cleaned
    
    # 3. Проверяем явные упоминания интернета/провайдеров
    priority_patterns = [
        r'\b(интернет|инет)\s+(не\s+работает|пропал|отключили|лагает|тормозит)\b',
        r'\b(ростелеком|дом\.ру|домру|билайн|мтс|мегафон|ттк)\s+\w+',
        r'\b(плохой|низкая|высокий)\s+(интернет|пинг|скорость)\b',
        r'\b(проблемы|лаги|обрывы)\s+(с|интернет|связь)\b'
    ]
    
    for pattern in priority_patterns:
        match = re.search(pattern, full_context.lower())
        if match:
            matched_text = match.group(0)
            for keyword in keywords:
                if any(word in keyword.lower() for word in matched_text.split()):
                    return keyword
    
    # 4. Fuzzy matching с валидацией
    best_match = None
    best_ratio = 0
    
    for kw in keywords:
        kw_norm = kw.lower().strip()
        if not kw_norm:
            continue
        
        # Вычисляем сходство
        exact_ratio = fuzz.ratio(norm_text, kw_norm)
        partial_ratio = fuzz.partial_ratio(norm_text, kw_norm)
        token_ratio = fuzz.token_sort_ratio(norm_text, kw_norm)
        
        max_ratio = max(exact_ratio, partial_ratio, token_ratio)
        
        # Адаптивный порог
        if len(kw_norm) <= 5:
            required_threshold = threshold + 10
        else:
            required_threshold = threshold
        
        # Валидация
        if max_ratio >= required_threshold and max_ratio > best_ratio:
            if _validate_match(norm_text, kw_norm, full_context):
                best_ratio = max_ratio
                best_match = kw
    
    return best_match

def _validate_match(norm_text, matched_norm, full_context):
    """Валидация совпадения"""
    # Исключаем ложные срабатывания
    if norm_text in FALSE_POSITIVE_WORDS and len(norm_text) <= 5:
        if not _is_contextually_relevant(full_context):
            return False
    
    # Проверяем соотношение длин
    if len(norm_text) <= 3 and len(matched_norm) > 10:
        if norm_text not in matched_norm:
            return False
    
    length_ratio = min(len(norm_text), len(matched_norm)) / max(len(norm_text), len(matched_norm))
    if length_ratio < MIN_LENGTH_RATIO:
        similarity = fuzz.ratio(norm_text, matched_norm)
        if similarity < SIMILARITY_THRESHOLDS['high_confidence']:
            return False
    
    return True

def _is_contextually_relevant(text):
    """Проверка контекстуальной релевантности"""
    for pattern in RELEVANCE_INDICATORS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

def analyze_match_quality(text, matched_keyword):
    """Анализ качества совпадения"""
    if not matched_keyword:
        return None
    
    norm_text = text.lower().strip()
    matched_norm = matched_keyword.lower().strip()
    
    exact_ratio = fuzz.ratio(norm_text, matched_norm)
    partial_ratio = fuzz.partial_ratio(norm_text, matched_norm)
    token_ratio = fuzz.token_sort_ratio(norm_text, matched_norm)
    
    return {
        'exact_similarity': exact_ratio,
        'partial_similarity': partial_ratio,
        'token_similarity': token_ratio,
        'quality_score': (exact_ratio + partial_ratio + token_ratio) / 3,
        'confidence': 'high' if exact_ratio > 85 else 'medium' if exact_ratio > 70 else 'low',
        'is_contextually_relevant': _is_contextually_relevant(f"{text} {matched_keyword}")
    }

# Оставляем старые функции для совместимости
def enhanced_find_match(text, keywords, threshold=85):
    """Совместимость со старым API"""
    return smart_find_match(text, keywords, threshold=threshold)

def find_match(text, keywords, threshold=80, use_regex=True, ignore_case=True):
    """Совместимость со старым API"""
    return smart_find_match(text, keywords, threshold=threshold)
