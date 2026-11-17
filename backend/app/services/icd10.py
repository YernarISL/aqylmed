"""Справочник МКБ-10 для выбора итогового диагноза (US-04).

Для MVP — подборка кодов по темам курса (app/data/icd10.json). Полный справочник
можно подложить в тот же файл в том же формате, код менять не нужно.
"""
import json
from functools import lru_cache
from pathlib import Path

ICD_PATH = Path(__file__).resolve().parent.parent / "data" / "icd10.json"


@lru_cache
def _codes() -> dict[str, str]:
    items = json.loads(ICD_PATH.read_text(encoding="utf-8"))
    return {i["code"].upper(): i["name"] for i in items}


def normalize(code: str) -> str:
    return code.strip().upper()


def exists(code: str) -> bool:
    return normalize(code) in _codes()


def name(code: str) -> str | None:
    return _codes().get(normalize(code))


def search(q: str = "", limit: int = 20) -> list[dict]:
    """Автодополнение по коду (префикс) или по названию (подстрока)."""
    q = q.strip().lower()
    items = _codes().items()
    if not q:
        result = list(items)
    else:
        by_code = [(c, n) for c, n in items if c.lower().startswith(q)]
        by_name = [(c, n) for c, n in items if q in n.lower() and (c, n) not in by_code]
        result = by_code + by_name
    return [{"code": c, "name": n} for c, n in result[:limit]]
