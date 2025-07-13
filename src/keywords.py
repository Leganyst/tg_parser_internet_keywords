from src.config import *

def load_keywords(filepath="keywords.txt"):
    try:
        with open(filepath, encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        return []
def add_keyword(keyword, filepath="keywords.txt"):
    keywords_to_add = []
    for part in keyword.replace(",", "\n").splitlines():
        w = part.strip()
        if w:
            keywords_to_add.append(w)
    if not keywords_to_add:
        return False
    existing = load_keywords(filepath)
    added = False
    with open(filepath, "a", encoding="utf-8") as f:
        for w in keywords_to_add:
            if w.lower() not in [k.lower() for k in existing]:
                f.write(w + "\n")
                existing.append(w)
                added = True
    return added
def remove_keyword(keyword, filepath="keywords.txt"):
    keyword = keyword.strip()
    keywords = load_keywords(filepath)
    filtered = [k for k in keywords if k.lower() != keyword.lower()]
    if len(filtered) == len(keywords):
        return False
    with open(filepath, "w", encoding="utf-8") as f:
        for k in filtered:
            f.write(k + "\n")
    return True
    
def load_spam_patterns(filepath=SPAM_FILE) -> list[str]:
    """Загрузка шаблонов спама из файла."""
    try:
        with open(filepath, encoding="utf-8") as f:
            patterns = []
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                pat = line.split('#', 1)[0].strip()
                if pat:
                    patterns.append(pat)
            return patterns
    except FileNotFoundError:
        return []

def add_spam_pattern(pattern: str, filepath=SPAM_FILE) -> bool:
    """Добавление нового шаблона спама."""
    existing = load_spam_patterns(filepath)
    if pattern in existing:
        return False
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(pattern + '\n')
        return True
    except Exception:
        return False

def remove_spam_pattern(pattern: str, filepath=SPAM_FILE) -> bool:
    """Удаление шаблона спама."""
    existing = load_spam_patterns(filepath)
    filtered = [p for p in existing if p != pattern]
    if len(filtered) == len(existing):
        return False
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for p in filtered:
                f.write(p + '\n')
        return True
    except Exception:
        return False