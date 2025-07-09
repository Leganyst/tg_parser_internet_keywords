import re
from rapidfuzz import fuzz

# Простая функция поиска ключевых слов

def simple_keyword_match(text, keywords, fuzz_threshold=90):
    """
    Простой поиск: ищет точное вхождение слова из списка ключей в тексте,
    допускает незначительные опечатки (fuzz.ratio >= fuzz_threshold),
    но не совпадения по подстроке или набору букв.
    """
    norm_text = text.lower()
    words = re.findall(r'\w+', norm_text)
    for kw in keywords:
        kw_norm = kw.lower().strip()
        # Проверяем точное вхождение как отдельного слова
        if re.search(rf'\b{re.escape(kw_norm)}\b', norm_text):
            return kw
        # Проверяем каждое слово в тексте на незначительную опечатку
        for w in words:
            if fuzz.ratio(w, kw_norm) >= fuzz_threshold:
                return kw
    return None
