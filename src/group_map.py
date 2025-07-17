import json
from pathlib import Path
from loguru import logger

# Путь к файлу group_map.json
GROUP_MAP_PATH = Path(__file__).parent / "group_map.json"


def load_group_map() -> dict[str, str]:
    """Загружает маппинг шаблонов → групп из JSON."""
    try:
        with open(GROUP_MAP_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Файл групп не найден: {GROUP_MAP_PATH}")
        return {}


def add_group_pattern(pattern: str, group: str) -> bool:
    """Добавляет новый шаблон и группу."""
    gm = load_group_map()
    if not pattern or pattern in gm:
        return False
    gm[pattern] = group
    try:
        with open(GROUP_MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(gm, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения group_map: {e}")
        return False


def remove_group_pattern(pattern: str) -> bool:
    """Удаляет шаблон из маппинга."""
    gm = load_group_map()
    if pattern not in gm:
        return False
    gm.pop(pattern)
    try:
        with open(GROUP_MAP_PATH, 'w', encoding='utf-8') as f:
            json.dump(gm, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения group_map: {e}")
        return False
