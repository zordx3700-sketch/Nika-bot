import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MAIN_CHANNEL_ID = int(os.getenv("MAIN_CHANNEL_ID", "0"))
BACKUP_CHANNEL_ID = int(os.getenv("BACKUP_CHANNEL_ID", "0"))
MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK", "https://t.me/")
BACKUP_CHANNEL_LINK = os.getenv("BACKUP_CHANNEL_LINK", "https://t.me/")

# Main Private Channel where content is hosted
TARGET_CHANNEL_ID = int(os.getenv("CH_720P_HINDI", "0")) # Adjust to your primary storage channel

FIREBASE_CREDS_RAW = os.getenv("FIREBASE_CREDENTIALS_JSON")
