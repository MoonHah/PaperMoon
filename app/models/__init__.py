# 统一注册所有 ORM 模型：任何 import app.models.* 都会触发 User 与 Document 注册，
# 否则 worker 等只导入 document 的进程在解析 documents.user_id 外键时找不到 users 表。
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.user import User  # noqa: F401
