"""Production entrypoint for serving the Flask app with Waitress."""

import os

from waitress import serve

from chatbot_app import create_app

app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    serve(app, host="0.0.0.0", port=port)
