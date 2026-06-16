"""认证服务：密码哈希（bcrypt）+ JWT 签发/校验 + 注册/登录编排。

哈希用 bcrypt、JWT 用 PyJWT，都是成熟库——不手搓加密。
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.user import User
from app.repositories import user_repository

# bcrypt 仅使用口令前 72 字节；超长先截断避免 bcrypt 5.x 抛错。
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    pw = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(pw, hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    """校验 JWT，返回 user_id（sub）。无效/过期抛 AppError(401)。"""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        raise AppError(error_code="INVALID_TOKEN", message="无效或过期的凭证。", status_code=401)
    sub = payload.get("sub")
    if not sub:
        raise AppError(error_code="INVALID_TOKEN", message="无效凭证。", status_code=401)
    return sub


def register(session: Session, email: str, password: str) -> User:
    if user_repository.get_by_email(session, email) is not None:
        raise AppError(error_code="EMAIL_TAKEN", message="该邮箱已注册。", status_code=409)
    user = user_repository.create(
        session,
        user_id=str(uuid4()),
        email=email,
        hashed_password=hash_password(password),
    )
    session.commit()
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = user_repository.get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        # 不区分"邮箱不存在"与"密码错误"，避免账号枚举
        raise AppError(error_code="INVALID_CREDENTIALS", message="邮箱或密码错误。", status_code=401)
    return user
