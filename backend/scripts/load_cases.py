"""Загрузить шаблоны кейсов из data/cases/*.json в БД (по коду: новый — добавить, существующий — обновить).
Статус берётся из файла ("draft"/"published").

Запуск из корня проекта:  python -m scripts.load_cases
"""
import json
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import ClinicCase
from app.schemas import CaseTemplate

CASES_DIR = Path(__file__).resolve().parent.parent / "data" / "cases"


def load(db, directory: Path = CASES_DIR) -> list[str]:
    log = []
    for path in sorted(directory.glob("*.json")):
        t = CaseTemplate(**json.loads(path.read_text(encoding="utf-8")))  # валидация формата
        case = db.scalar(select(ClinicCase).where(ClinicCase.code == t.code))
        action = "updated" if case else "added"
        case = case or ClinicCase()
        case.code, case.title, case.specialty, case.difficulty = t.code, t.title, t.specialty, t.difficulty
        case.status, case.data = t.status, t.model_dump()
        db.add(case)
        log.append(f"{action}: {t.code} [{t.status}] {t.title}")
    db.commit()
    return log


def main():
    init_db()
    with SessionLocal() as db:
        for line in load(db):
            print(line)


if __name__ == "__main__":
    main()
