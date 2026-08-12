import os
import threading

from flask import Flask

from main import create_bot


app = Flask(__name__)


@app.route("/")
def home():
    return "Master Video Hub Bot is running!"


@app.route("/health")
def health():
    return "OK"


def start_bot():
    bot_app = create_bot()
    bot_app.run_polling()


threading.Thread(
    target=start_bot,
    daemon=True
).start()
