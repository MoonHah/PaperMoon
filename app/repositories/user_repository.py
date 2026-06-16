from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_by_email(session: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return session.execute(stmt).scalar_one_or_none()


def get_by_id(session: Session, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return session.execute(stmt).scalar_one_or_none()


def create(session: Session, user_id: str, email: str, hashed_password: str) -> User:
    user = User(id=user_id, email=email, hashed_password=hashed_password)
    session.add(user)
    session.flush()
    return user
