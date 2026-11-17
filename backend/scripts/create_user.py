"""Создать пользователя с ролью (teacher/admin нельзя получить через /register).

python -m scripts.create_user --email admin@aqylmed.kz --password secret123 --role admin
"""
import argparse

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models import User
from app.security import hash_password


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--role", choices=["student", "teacher", "admin"], default="student")
    p.add_argument("--first-name", default="")
    p.add_argument("--last-name", default="")
    a = p.parse_args()

    init_db()
    with SessionLocal() as db:
        email = a.email.lower()
        user = db.scalar(select(User).where(User.email == email))
        if user:
            user.role, user.password_hash = a.role, hash_password(a.password)
            print(f"Updated {email}: role={a.role}")
        else:
            db.add(User(email=email, password_hash=hash_password(a.password), role=a.role,
                        first_name=a.first_name, last_name=a.last_name))
            print(f"Created {email}: role={a.role}")
        db.commit()


if __name__ == "__main__":
    main()
