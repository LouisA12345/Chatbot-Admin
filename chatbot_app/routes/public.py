from flask import Blueprint, jsonify

from chatbot_app.config import DEFAULT_CONFIG
from chatbot_app.services.site_store import load_config

public_bp = Blueprint("public", __name__)


@public_bp.route("/config/<site_id>", methods=["GET"])
def public_config(site_id):
    config = load_config(site_id)
    return jsonify({key: config.get(key, DEFAULT_CONFIG[key]) for key in DEFAULT_CONFIG})
