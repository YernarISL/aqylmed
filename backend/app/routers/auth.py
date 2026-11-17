"""Регистрация и вход (технический энейблер, 0 SP; задача DEV в Sprint 1: «account storage, registration, JWT login»)."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, first_name=u.first_name, last_name=u.last_name,
                   university=u.university, role=u.role)


def _login(db: Session, email: str, password: str) -> TokenOut:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash) or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return TokenOut(access_token=create_token(user), user=user_out(user))


@router.post("/register", response_model=TokenOut, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Самостоятельная регистрация — всегда роль student. Преподавателей/админов создаёт скрипт."""
    email = req.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered")
    user = User(email=email, password_hash=hash_password(req.password), first_name=req.first_name.strip(),
                last_name=req.last_name.strip(), university=req.university.strip(), role="student")
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_token(user), user=user_out(user))


@router.post("/login", response_model=TokenOut)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return _login(db, req.email, req.password)


@router.post("/token", response_model=TokenOut, include_in_schema=False)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Для кнопки Authorize в /docs: username = email."""
    return _login(db, form.username, form.password)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)
