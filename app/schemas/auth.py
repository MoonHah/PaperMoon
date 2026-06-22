from pydantic import BaseModel, Field

# email 用 str（不用 EmailStr）：邮箱/密码的全部校验放在 auth_service，
# 以 AppError 抛友好中文（schema 校验失败是 422，前端只拿到笼统英文）。
# password 仅在 schema 保留长度上限作 DoS 防护，下限/复杂度同样交给 service。


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(max_length=128)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: str
