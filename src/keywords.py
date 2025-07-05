from .config import *

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