import os
import asyncio
import threading

from dotenv import load_dotenv
from flask import Flask

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from downloader import (
    download_video,
    DownloadError,
)


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

BRAND = "Powered by MASTERMIND"


# =========================================================
# FLASK HEALTH SERVER
# =========================================================

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Master Video Hub Bot is running!"


@web_app.route("/health")
def health():
    return "OK"


def run_web():
    port = int(os.environ.get("PORT", 10000))

    web_app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# BRANDING
# =========================================================

def branded_text(text):
    return f"{text}\n\n{BRAND}"


# =========================================================
# FORMAT BYTES
# =========================================================

def format_bytes(value):

    if not value:
        return "0 B"

    try:
        value = float(value)
    except Exception:
        return "0 B"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    for unit in units:

        if value < 1024:
            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{value:.1f} PB"


# =========================================================
# PROGRESS BAR
# =========================================================

def progress_bar(percent, length=12):

    try:
        percent = float(percent)
    except Exception:
        percent = 0

    percent = max(
        0,
        min(100, percent)
    )

    filled = int(
        length * percent / 100
    )

    empty = length - filled

    return (
        "█" * filled +
        "░" * empty
    )


# =========================================================
# START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (
        "🎬 <b>Master Video Hub</b>\n\n"
        "🔗 একটি supported video URL পাঠাও।\n\n"
        "তারপর তোমার পছন্দের quality নির্বাচন করো।"
    )

    await update.message.reply_text(
        branded_text(text),
        parse_mode="HTML"
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (
        "📖 <b>How To Use</b>\n\n"
        "1️⃣ Video URL পাঠাও\n"
        "2️⃣ Quality নির্বাচন করো\n"
        "3️⃣ Download শেষ হওয়া পর্যন্ত অপেক্ষা করো\n"
        "4️⃣ Bot file পাঠিয়ে দেবে"
    )

    await update.message.reply_text(
        branded_text(text),
        parse_mode="HTML"
    )


# =========================================================
# URL HANDLER
# =========================================================

async def handle_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if not update.message.text:
        return

    url = update.message.text.strip()

    # -----------------------------------------------------
    # URL CHECK
    # -----------------------------------------------------

    if not url.startswith(
        ("http://", "https://")
    ):

        await update.message.reply_text(
            branded_text(
                "❌ <b>Invalid URL</b>\n\n"
                "একটি valid video URL পাঠাও।"
            ),
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # SAVE URL
    # -----------------------------------------------------

    context.user_data["video_url"] = url

    # -----------------------------------------------------
    # QUALITY BUTTONS
    # -----------------------------------------------------

    keyboard = [

        [
            InlineKeyboardButton(
                "360p",
                callback_data="quality_360"
            ),

            InlineKeyboardButton(
                "480p",
                callback_data="quality_480"
            ),
        ],

        [
            InlineKeyboardButton(
                "720p",
                callback_data="quality_720"
            ),

            InlineKeyboardButton(
                "1080p",
                callback_data="quality_1080"
            ),
        ],

        [
            InlineKeyboardButton(
                "🎵 MP3",
                callback_data="quality_mp3"
            ),
        ],

        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel_download"
            ),
        ],
    ]

    await update.message.reply_text(
        branded_text(
            "🎬 <b>Video URL Received</b>\n\n"
            "📺 Quality নির্বাচন করো:"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            keyboard
        )
    )


# =========================================================
# QUALITY CALLBACK
# =========================================================

async def quality_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    # -----------------------------------------------------
    # CANCEL
    # -----------------------------------------------------

    if query.data == "cancel_download":

        context.user_data.pop(
            "video_url",
            None
        )

        await query.edit_message_text(
            branded_text(
                "❌ <b>Download Cancelled</b>"
            ),
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # GET URL
    # -----------------------------------------------------

    url = context.user_data.get(
        "video_url"
    )

    if not url:

        await query.edit_message_text(
            branded_text(
                "❌ <b>URL পাওয়া যায়নি</b>\n\n"
                "আবার URL পাঠাও।"
            ),
            parse_mode="HTML"
        )

        return

    # -----------------------------------------------------
    # GET QUALITY
    # -----------------------------------------------------

    quality = query.data.replace(
        "quality_",
        ""
    )

    quality_name = (
        "MP3"
        if quality == "mp3"
        else f"{quality}p"
    )

    # -----------------------------------------------------
    # INITIAL MESSAGE
    # -----------------------------------------------------

    await query.edit_message_text(
        branded_text(
            "⏳ <b>Starting Download...</b>\n\n"
            f"🎚 Quality: <b>{quality_name}</b>\n\n"
            "Please wait..."
        ),
        parse_mode="HTML"
    )

    filename = None

    progress_data = {
        "percent": 0,
        "downloaded": 0,
        "total": 0,
        "speed": None,
        "eta": None,
    }

    # =====================================================
    # PROGRESS CALLBACK
    # =====================================================

    def progress_callback(data):

        if data.get("status") != "downloading":
            return

        downloaded = data.get(
            "downloaded_bytes",
            0
        )

        total = data.get(
            "total_bytes"
        )

        if not total:
            total = data.get(
                "total_bytes_estimate"
            )

        if total:
            percent = (
                downloaded / total
            ) * 100
        else:
            percent = 0

        progress_data.update({

            "percent": percent,

            "downloaded": downloaded,

            "total": total or 0,

            "speed": data.get(
                "speed"
            ),

            "eta": data.get(
                "eta"
            ),
        })

    # =====================================================
    # LIVE PROGRESS TASK
    # =====================================================

    async def update_progress():

        while True:

            await asyncio.sleep(3)

            percent = progress_data[
                "percent"
            ]

            downloaded = progress_data[
                "downloaded"
            ]

            total = progress_data[
                "total"
            ]

            speed = progress_data[
                "speed"
            ]

            eta = progress_data[
                "eta"
            ]

            # Speed

            if speed:

                speed_text = (
                    f"{format_bytes(speed)}/s"
                )

            else:

                speed_text = "N/A"

            # ETA

            if eta is not None:

                try:
                    eta_text = f"{int(eta)}s"
                except Exception:
                    eta_text = "N/A"

            else:

                eta_text = "N/A"

            # Size

            if total:

                size_text = (
                    f"{format_bytes(downloaded)} / "
                    f"{format_bytes(total)}"
                )

            else:

                size_text = format_bytes(
                    downloaded
                )

            bar = progress_bar(
                percent
            )

            text = (
                "⬇️ <b>Downloading...</b>\n\n"
                f"{bar} <b>{percent:.1f}%</b>\n\n"
                f"📦 {size_text}\n"
                f"⚡ Speed: {speed_text}\n"
                f"⏱ ETA: {eta_text}\n"
                f"🎚 Quality: {quality_name}"
            )

            try:

                await query.message.edit_text(
                    branded_text(text),
                    parse_mode="HTML"
                )

            except Exception:

                pass

    progress_task = asyncio.create_task(
        update_progress()
    )

    # =====================================================
    # DOWNLOAD
    # =====================================================

    try:

        loop = asyncio.get_running_loop()

        filename, title = await loop.run_in_executor(
            None,
            download_video,
            url,
            quality,
            progress_callback
        )

        # -------------------------------------------------
        # STOP PROGRESS
        # -------------------------------------------------

        progress_task.cancel()

        try:

            await query.message.edit_text(
                branded_text(
                    "📤 <b>Download Complete!</b>\n\n"
                    "⬆️ Telegram-এ file upload হচ্ছে..."
                ),
                parse_mode="HTML"
            )

        except Exception:

            pass

        # =================================================
        # SEND MP3
        # =================================================

        if quality == "mp3":

            with open(
                filename,
                "rb"
            ) as audio:

                await query.message.reply_audio(

                    audio=audio,

                    caption=branded_text(
                        f"🎵 <b>{title}</b>\n\n"
                        "🎧 Format: MP3"
                    ),

                    parse_mode="HTML"
                )

        # =================================================
        # SEND VIDEO
        # =================================================

        else:

            with open(
                filename,
                "rb"
            ) as video:

                await query.message.reply_video(

                    video=video,

                    caption=branded_text(
                        f"🎬 <b>{title}</b>\n\n"
                        f"📺 Quality: {quality}p"
                    ),

                    parse_mode="HTML"
                )

        # -------------------------------------------------
        # DELETE STATUS MESSAGE
        # -------------------------------------------------

        try:

            await query.message.delete()

        except Exception:

            pass

    # =====================================================
    # DOWNLOAD ERROR
    # =====================================================

    except DownloadError as e:

        progress_task.cancel()

        try:

            await query.message.edit_text(
                branded_text(
                    "❌ <b>Download Failed</b>\n\n"
                    f"{str(e)}"
                ),
                parse_mode="HTML"
            )

        except Exception:

            pass

    # =====================================================
    # UNKNOWN ERROR
    # =====================================================

    except Exception as e:

        progress_task.cancel()

        print(
            "DOWNLOAD ERROR:",
            repr(e)
        )

        try:

            await query.message.edit_text(
                branded_text(
                    "❌ <b>Unexpected Error</b>\n\n"
                    f"<code>{str(e)[:700]}</code>"
                ),
                parse_mode="HTML"
            )

        except Exception:

            pass

    # =====================================================
    # CLEANUP
    # =====================================================

    finally:

        context.user_data.pop(
            "video_url",
            None
        )

        if filename and os.path.exists(
            filename
        ):

            try:

                os.remove(
                    filename
                )

            except Exception:

                pass


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# =========================================================
# CREATE BOT
# =========================================================

def create_bot():

    if not BOT_TOKEN:

        raise ValueError(
            "BOT_TOKEN পাওয়া যায়নি। "
            "Render Environment Variables-এ "
            "BOT_TOKEN সেট করো।"
        )

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # -----------------------------------------------------
    # URL HANDLER
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_url
        )
    )

    # -----------------------------------------------------
    # BUTTONS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            quality_callback,
            pattern=r"^(quality_|cancel_download)"
        )
    )

    # -----------------------------------------------------
    # ERROR HANDLER
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    return application


# =========================================================
# MAIN
# =========================================================

def main():

    # -----------------------------------------------------
    # START WEB SERVER
    # -----------------------------------------------------

    web_thread = threading.Thread(
        target=run_web,
        daemon=True
    )

    web_thread.start()

    print(
        "🌐 Web server started"
    )

    # -----------------------------------------------------
    # START TELEGRAM BOT
    # -----------------------------------------------------

    application = create_bot()

    print(
        "🤖 Video Downloader Bot is running..."
    )

    print(
        "🚀 Powered by MASTERMIND"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    main()
