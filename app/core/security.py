from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import AppError
from app.models.user import User
from app.repositories import user_repository
from app.services import auth_service

# auto_error=False：缺/坏 token 时由我们统一抛 AppError(401)，走统一错误格式
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise AppError(error_code="NOT_AUTHENTICATED", message="需要登录。", status_code=401)
    user_id = auth_service.decode_token(creds.credentials)
    user = user_repository.get_by_id(db, user_id)
    if user is None:
        raise AppError(error_code="NOT_AUTHENTICATED", message="用户不存在。", status_code=401)
    return user
