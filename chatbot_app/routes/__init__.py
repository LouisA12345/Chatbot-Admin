from chatbot_app.routes.admin import admin_bp
from chatbot_app.routes.auth import auth_bp
from chatbot_app.routes.chat import chat_bp
from chatbot_app.routes.public import public_bp

__all__ = ["admin_bp", "auth_bp", "chat_bp", "public_bp"]
