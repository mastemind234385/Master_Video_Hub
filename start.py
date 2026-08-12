import threading

from main import create_bot
from web import run_web


# Start Flask web server
threading.Thread(
    target=run_web,
    daemon=True
).start()


# Start Telegram bot
bot = create_bot()

print("🤖 Video Downloader Bot is running...")
print("🚀 Powered by MASTERMIND")

bot.run_polling()
