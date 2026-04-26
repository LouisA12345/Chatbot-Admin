from functools import wraps

from flask import current_app, jsonify, request


def require_admin_key(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        if request.headers.get("X-Admin-Key") != current_app.config["ADMIN_API_KEY"]:
            return jsonify({"error": "Unauthorized"}), 401
        return func(*args, **kwargs)

    return decorated
