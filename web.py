from flask import Flask
import threading
import os


app = Flask(__name__)


@app.route("/")
def home():
    return "Master Video Hub Bot is running!"


@app.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )
