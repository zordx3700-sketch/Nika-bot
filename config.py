import os


def get_int(name: str, default: int = 0) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError:
        return default


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

ADMIN_ID = get_int("ADMIN_ID")

MAIN_CHANNEL_ID = get_int("MAIN_CHANNEL_ID")
BACKUP_CHANNEL_ID = get_int("BACKUP_CHANNEL_ID")

MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK", "").strip()
BACKUP_CHANNEL_LINK = os.getenv("BACKUP_CHANNEL_LINK", "").strip()

# Private content channels
CHANNEL_480_HINDI = get_int("CHANNEL_480_HINDI")
CHANNEL_480_ENGLISH = get_int("CHANNEL_480_ENGLISH")

CHANNEL_720_HINDI = get_int("CHANNEL_720_HINDI")
CHANNEL_720_ENGLISH = get_int("CHANNEL_720_ENGLISH")

CHANNEL_1080_HINDI = get_int("CHANNEL_1080_HINDI")
CHANNEL_1080_ENGLISH = get_int("CHANNEL_1080_ENGLISH")

# Optional: poster source channel
POSTER_CHANNEL_ID = get_int("POSTER_CHANNEL_ID")

FIREBASE_CREDENTIALS_B64 = os.getenv(
    "FIREBASE_CREDENTIALS_B64", ""
).strip()


QUALITY_CHANNELS = {
    ("480p", "Hindi"): CHANNEL_480_HINDI,
    ("480p", "English"): CHANNEL_480_ENGLISH,

    ("720p", "Hindi"): CHANNEL_720_HINDI,
    ("720p", "English"): CHANNEL_720_ENGLISH,

    ("1080p", "Hindi"): CHANNEL_1080_HINDI,
    ("1080p", "English"): CHANNEL_1080_ENGLISH,
}


AVAILABLE_QUALITIES = ["480p", "720p", "1080p"]
AVAILABLE_LANGUAGES = ["Hindi", "English"]


def validate_config():
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "ADMIN_ID": ADMIN_ID,
        "MAIN_CHANNEL_ID": MAIN_CHANNEL_ID,
        "BACKUP_CHANNEL_ID": BACKUP_CHANNEL_ID,
        "MAIN_CHANNEL_LINK": MAIN_CHANNEL_LINK,
        "BACKUP_CHANNEL_LINK": BACKUP_CHANNEL_LINK,
        "CHANNEL_480_HINDI": CHANNEL_480_HINDI,
        "CHANNEL_480_ENGLISH": CHANNEL_480_ENGLISH,
        "CHANNEL_720_HINDI": CHANNEL_720_HINDI,
        "CHANNEL_720_ENGLISH": CHANNEL_720_ENGLISH,
        "CHANNEL_1080_HINDI": CHANNEL_1080_HINDI,
        "CHANNEL_1080_ENGLISH": CHANNEL_1080_ENGLISH,
    }

    missing = [
        key for key, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Missing environment variables: "
            + ", ".join(missing)
        )
