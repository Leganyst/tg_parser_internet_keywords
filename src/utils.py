import re
from .keywords import load_keywords
from rapidfuzz import fuzz, process

def find_match(text, keywords, threshold=80, use_regex=True, ignore_case=True):
    norm_text = text.lower().replace('\n', ' ')
    if use_regex:
        # Экранируем ключи и собираем в одно выражение с границами слова
        pattern = r"|".join([rf"\\b{re.escape(kw)}\\b" for kw in keywords if kw.strip()])
        flags = re.IGNORECASE if ignore_case else 0
        if pattern:
            match = re.search(pattern, text, flags)
            if match:
                return match.group(0)
    # Fuzzy fallback (оставляем для совместимости)
    for kw in keywords:
        if kw in norm_text:
            return kw
        ratio = fuzz.partial_ratio(norm_text, kw)
        if ratio >= threshold:
            return kw
    return None
