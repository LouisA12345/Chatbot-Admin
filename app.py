"""Local development entrypoint for the Flask app."""

from chatbot_app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)