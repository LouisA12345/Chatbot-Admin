"""Local development entrypoint for the Flask app."""

from chatbot_app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
