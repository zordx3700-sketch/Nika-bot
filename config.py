import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Securely load Telegram Bot Token
RAW_TOKEN = os.getenv("BOT_TOKEN")
if not RAW_TOKEN:
    print("ERROR: BOT_TOKEN is missing from Environment Variables!")
    sys.exit(1)

BOT_TOKEN = RAW_TOKEN.strip().strip('"').strip("'")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Verification Channels
MAIN_CHANNEL_ID = int(os.getenv("MAIN_CHANNEL_ID", "0"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID", "0"))
MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK", "https://t.me/")
BACKUP_CHANNEL_LINK = os.getenv("BACKUP_CHANNEL_LINK", "https://t.me/")

# All 6 Storage Private Channels
CHANNELS = {
    "480p_Hindi": int(os.getenv("CH_480P_HINDI", "0")),
    "480p_English": int(os.getenv("CH_480P_ENGLISH", "0")),
    "720p_Hindi": int(os.getenv("CH_720P_HINDI", "0")),
    "720p_English": int(os.getenv("CH_720P_ENGLISH", "0")),
    "1080p_Hindi": int(os.getenv("CH_1080P_HINDI", "0")),
    "1080p_English": int(os.getenv("CH_1080P_ENGLISH", "0")),
}

FIREBASE_CREDS_RAW = os.getenv("FIREBASE_CREDENTIALS_JSON")
