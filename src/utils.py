from .keywords import load_keywords
from rapidfuzz import fuzz, process
def find_match(text, keywords, threshold=80):
    norm_text = text.lower().replace('\n', ' ')
    for kw in keywords:
        if kw in norm_text:
            return kw
        ratio = fuzz.partial_ratio(norm_text, kw)
        if ratio >= threshold:
            return kw
    return None
