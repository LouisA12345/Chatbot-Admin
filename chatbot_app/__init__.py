"""Flask application factory and top-level blueprint registration."""

from flask import Flask
from flask_cors import CORS

from chatbot_app.config import get_admin_api_key
from chatbot_app.routes.admin import admin_bp
from chatbot_app.routes.auth import auth_bp
from chatbot_app.routes.chat import chat_bp
from chatbot_app.routes.public import public_bp


def create_app():
    """Build and configure the Flask application instance."""
    app = Flask(__name__)
    CORS(app)
    app.config["ADMIN_API_KEY"] = get_admin_api_key()
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(chat_bp)
    return app
