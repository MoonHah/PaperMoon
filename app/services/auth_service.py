"""认证服务：密码哈希（bcrypt）+ JWT 签发/校验 + 注册/登录编排。

哈希用 bcrypt、JWT 用 PyJWT，都是成熟库——不手搓加密。
"""

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
import jwt
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.user import User
from app.repositories import user_repository

# bcrypt 仅使用口令前 72 字节；超长先截断避免 bcrypt 5.x 抛错。
_BCRYPT_MAX_BYTES = 72

# 密码策略常量。NIST 800-63B 务实路线：重长度 + 弱密码黑名单，而非强制大小写/符号。
_PASSWORD_MIN_LEN = 8
_PASSWORD_MAX_LEN = 128
_HAS_LETTER = re.compile(r"[A-Za-z]")
_HAS_DIGIT = re.compile(r"\d")
# 常见弱密码小黑名单（小而精；生产可换 zxcvbn 或 HaveIBeenPwned 泄漏库）。
_WEAK_PASSWORDS = {
    "password", "password1", "passw0rd", "12345678", "123456789", "1234567890",
    "qwerty123", "11111111", "00000000", "abc12345", "iloveyou", "admin123",
    "letmein1", "welcome1", "qwertyui", "1q2w3e4r",
}


def normalize_email(email: str) -> str:
    """校验邮箱格式 +（按开关）MX 可投递性，返回规范化小写邮箱。失败抛 AppError(400)。

    放在 service 层而非 schema：schema 校验失败是 422，前端只拿到笼统的
    "Request validation failed"；这里抛 AppError 才能把友好中文经 body.message 透出。
    """
    try:
        result = validate_email(
            email,
            check_deliverability=settings.auth_check_email_deliverability,
        )
    except EmailNotValidError:
        # EmailUndeliverableError 是其子类，格式错与不可投递一并归一为此错。
        raise AppError(
            error_code="INVALID_EMAIL",
            message="请输入有效且可投递的邮箱地址。",
            status_code=400,
        )
    # 域名已小写；本地部分大小写默认保留，这里整体小写以做大小写无关去重。
    return result.normalized.lower()


def validate_password_policy(password: str, email: str) -> None:
    """密码强度校验，不满足抛 AppError(400, WEAK_PASSWORD) 并带具体原因。"""
    if len(password) < _PASSWORD_MIN_LEN:
        raise _weak("密码至少 8 位。")
    if len(password) > _PASSWORD_MAX_LEN:
        raise _weak("密码不能超过 128 位。")
    if not (_HAS_LETTER.search(password) and _HAS_DIGIT.search(password)):
        raise _weak("密码需同时包含字母和数字。")
    if password.lower() in _WEAK_PASSWORDS:
        raise _weak("密码过于常见，请换一个更复杂的。")
    # 只在本地部分足够长时查包含，避免 a@x.com 这种单字符把含 a 的密码全拒。
    local = email.split("@", 1)[0].lower()
    if len(local) >= 4 and local in password.lower():
        raise _weak("密码不能包含你的邮箱名。")


def _weak(message: str) -> AppError:
    return AppError(error_code="WEAK_PASSWORD", message=message, status_code=400)


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
    # 先校验：邮箱规范化（格式 + 可投递性）→ 密码策略（用规范化邮箱判“含邮箱名”）。
    email = normalize_email(email)
    validate_password_policy(password, email)
    # 先查重拦常见情况；并发同邮箱仍可能双双过检查，故 commit 再兜 unique 约束的 IntegrityError。
    if user_repository.get_by_email(session, email) is not None:
        raise AppError(error_code="EMAIL_TAKEN", message="该邮箱已注册。", status_code=409)
    try:
        # create() 内部 flush 即触发 INSERT，故 create+commit 一并纳入 try。
        user = user_repository.create(
            session,
            user_id=str(uuid4()),
            email=email,
            hashed_password=hash_password(password),
        )
        session.commit()
    except IntegrityError:
        session.rollback()
        raise AppError(error_code="EMAIL_TAKEN", message="该邮箱已注册。", status_code=409)
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    # 与注册同口径小写归一，确保大小写不同也能匹配；登录不做 MX 校验（避免泄漏+延迟）。
    email = email.strip().lower()
    user = user_repository.get_by_email(session, email)
    if user is None or not verify_password(password, user.hashed_password):
        # 不区分"邮箱不存在"与"密码错误"，避免账号枚举
        raise AppError(error_code="INVALID_CREDENTIALS", message="邮箱或密码错误。", status_code=401)
    return user
