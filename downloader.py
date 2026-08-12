import os
import uuid
import yt_dlp


DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


class DownloadError(Exception):
    pass


def download_video(
    url,
    quality="best",
    progress_callback=None
):

    file_id = str(uuid.uuid4())

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{file_id}.%(ext)s"
    )

    # =====================================================
    # PROGRESS
    # =====================================================

    def progress_hook(data):

        if progress_callback:

            try:
                progress_callback(data)
            except Exception:
                pass

    # =====================================================
    # COMMON OPTIONS
    # =====================================================

    common = {

        "outtmpl": output_template,

        "noplaylist": True,

        "quiet": True,
        "no_warnings": True,

        "retries": 5,
        "fragment_retries": 5,

        "continuedl": True,

        "socket_timeout": 30,

        "progress_hooks": [
            progress_hook
        ],
    }

    # =====================================================
    # MP3
    # =====================================================

    if quality == "mp3":

        options = {
            **common,

            "format": (
                "bestaudio/"
                "best"
            ),

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    # =====================================================
    # VIDEO
    # =====================================================

    else:

        quality_map = {
            "360": 360,
            "480": 480,
            "720": 720,
            "1080": 1080,
        }

        height = quality_map.get(
            quality,
            1080
        )

        # -------------------------------------------------
        # IMPORTANT
        #
        # Don't require a separate video stream.
        # First try combined formats, then separate streams.
        # -------------------------------------------------

        video_format = (
            f"best[height<={height}]/"
            f"bestvideo[height<={height}]+bestaudio/"
            "best"
        )

        options = {
            **common,

            "format": video_format,

            "merge_output_format": "mp4",
        }

    # =====================================================
    # DOWNLOAD
    # =====================================================

    try:

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=True
            )

            filename = ydl.prepare_filename(
                info
            )

    except Exception as e:

        error = str(e)
        lower = error.lower()

        # -------------------------------------------------
        # FORMAT ERROR
        # -------------------------------------------------

        if (
            "requested format is not available"
            in lower
        ):

            # Try the site's best available format.
            try:

                fallback_options = {
                    **common,
                    "format": "best",
                }

                if quality != "mp3":

                    fallback_options[
                        "merge_output_format"
                    ] = "mp4"

                with yt_dlp.YoutubeDL(
                    fallback_options
                ) as ydl:

                    info = ydl.extract_info(
                        url,
                        download=True
                    )

                    filename = (
                        ydl.prepare_filename(
                            info
                        )
                    )

            except Exception as fallback_error:

                raise DownloadError(
                    "❌ এই ভিডিওর available format "
                    "দিয়ে download করা যাচ্ছে না।\n\n"
                    f"Details: "
                    f"{str(fallback_error)[:400]}"
                )

        # -------------------------------------------------
        # BOT CHECK
        # -------------------------------------------------

        elif (
            "sign in to confirm" in lower
            or
            "not a bot" in lower
        ):

            raise DownloadError(
                "❌ YouTube বর্তমানে bot verification "
                "চাচ্ছে।"
            )

        # -------------------------------------------------
        # PRIVATE
        # -------------------------------------------------

        elif "private video" in lower:

            raise DownloadError(
                "🔒 এটি একটি private video।"
            )

        # -------------------------------------------------
        # UNAVAILABLE
        # -------------------------------------------------

        elif (
            "video unavailable" in lower
            or
            "video is unavailable" in lower
        ):

            raise DownloadError(
                "❌ ভিডিওটি unavailable বা সরানো হয়েছে।"
            )

        # -------------------------------------------------
        # LOGIN
        # -------------------------------------------------

        elif (
            "login required" in lower
            or
            "authentication required" in lower
        ):

            raise DownloadError(
                "🔐 এই ভিডিওটি login/authentication চায়।"
            )

        # -------------------------------------------------
        # GEO
        # -------------------------------------------------

        elif (
            "geo-restricted" in lower
            or
            "not available in your country" in lower
        ):

            raise DownloadError(
                "🌍 ভিডিওটি তোমার region-এ available নয়।"
            )

        # -------------------------------------------------
        # DRM
        # -------------------------------------------------

        elif "drm" in lower:

            raise DownloadError(
                "🔐 এই ভিডিওটি DRM protected।"
            )

        # -------------------------------------------------
        # OTHER
        # -------------------------------------------------

        else:

            raise DownloadError(
                f"❌ Download failed:\n"
                f"{error[:500]}"
            )

    # =====================================================
    # FIND FILE
    # =====================================================

    base_name = os.path.splitext(
        filename
    )[0]

    possible_files = []

    if quality == "mp3":

        possible_files.append(
            base_name + ".mp3"
        )

    else:

        possible_files.extend([
            base_name + ".mp4",
            base_name + ".mkv",
            base_name + ".webm",
            filename,
        ])

    final_file = None

    for path in possible_files:

        if os.path.exists(path):

            final_file = path
            break

    # =====================================================
    # FALLBACK FILE SEARCH
    # =====================================================

    if final_file is None:

        folder = DOWNLOAD_DIR

        for name in os.listdir(folder):

            if name.startswith(file_id):

                path = os.path.join(
                    folder,
                    name
                )

                if os.path.isfile(path):

                    final_file = path
                    break

    # =====================================================
    # CHECK
    # =====================================================

    if not final_file:

        raise DownloadError(
            "❌ Download হয়েছে কিন্তু file পাওয়া যায়নি।"
        )

    # =====================================================
    # TITLE
    # =====================================================

    title = info.get(
        "title",
        "Video"
    )

    return final_file, title