from flask import Blueprint, jsonify, request

from chatbot_app.services.chat_service import handle_chat_payload

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    payload, status_code = handle_chat_payload(request.json)
    return jsonify(payload), status_code
