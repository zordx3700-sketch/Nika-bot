"""
Telegram Bot Production Configuration Module.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0
- firebase-admin: >=6.5.0
- Render deployment environment

All sensitive parameters are dynamically loaded and validated from environment variables.
"""

import os
import sys
import json
import base64
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("Config")


def get_str(key: str, default: Optional[str] = None, required: bool = True) -> str:
    """
    Retrieve a string environment variable.

    :param key: Environment variable name
    :param default: Optional default fallback value
    :param required: Whether this variable is strictly required
    :return: String value
    :raises ValueError: If variable is required and not present or empty
    """
    val = os.environ.get(key)
    if val is not None:
        val = val.strip()
    
    if not val:
        if required:
            raise ValueError(f"Missing required environment variable: '{key}'")
        return default or ""
    return val


def get_int(key: str, default: Optional[int] = None, required: bool = True) -> int:
    """
    Retrieve and parse an integer environment variable.

    :param key: Environment variable name
    :param default: Optional default fallback value
    :param required: Whether this variable is strictly required
    :return: Parsed integer value
    :raises ValueError: If variable is missing, not a valid integer, or required check fails
    """
    val_str = os.environ.get(key)
    if val_str is not None:
        val_str = val_str.strip()

    if not val_str:
        if required and default is None:
            raise ValueError(f"Missing required integer environment variable: '{key}'")
        return default if default is not None else 0

    try:
        return int(val_str)
    except ValueError as err:
        raise ValueError(
            f"Invalid integer for environment variable '{key}': received '{val_str}'"
        ) from err


def decode_firebase_credentials(b64_string: str) -> Dict[str, Any]:
    """
    Decode Base64 encoded Firebase Service Account JSON credentials.

    :param b64_string: Base64 encoded service account json
    :return: Parsed dictionary containing service account credentials
    :raises ValueError: If decoding or JSON parsing fails
    """
    if not b64_string:
        raise ValueError("FIREBASE_CREDENTIALS_B64 is empty or not provided.")

    try:
        decoded_bytes = base64.b64decode(b64_string)
        decoded_str = decoded_bytes.decode("utf-8")
        cred_dict = json.loads(decoded_str)
        if not isinstance(cred_dict, dict) or "project_id" not in cred_dict:
            raise ValueError("Decoded Firebase JSON is missing 'project_id' key.")
        return cred_dict
    except Exception as e:
        raise ValueError(
            f"Failed to decode and parse FIREBASE_CREDENTIALS_B64. "
            f"Ensure it is a valid base64-encoded service account JSON: {e}"
        ) from e


def validate_config() -> None:
    """
    Validate all required environment variables and dependencies.
    Logs clear errors and exits if critical parameters are missing.
    """
    errors = []
    
    # Check BOT_TOKEN
    try:
        token = get_str("BOT_TOKEN", required=True)
        if ":" not in token:
            errors.append("BOT_TOKEN format is invalid. It should match '<bot_id>:<token>'.")
    except ValueError as e:
        errors.append(str(e))

    # Check ADMIN_ID
    try:
        get_int("ADMIN_ID", required=True)
    except ValueError as e:
        errors.append(str(e))

    # Check MAIN_CHANNEL_ID
    try:
        get_int("MAIN_CHANNEL_ID", required=True)
    except ValueError as e:
        errors.append(str(e))

    # Check BACKUP_CHANNEL_ID
    try:
        get_int("BACKUP_CHANNEL_ID", required=True)
    except ValueError as e:
        errors.append(str(e))

    # Check MAIN_CHANNEL_LINK
    try:
        get_str("MAIN_CHANNEL_LINK", required=True)
    except ValueError as e:
        errors.append(str(e))

    # Check BACKUP_CHANNEL_LINK
    try:
        get_str("BACKUP_CHANNEL_LINK", required=True)
    except ValueError as e:
        errors.append(str(e))

    # Check FIREBASE_CREDENTIALS_B64
    try:
        b64_creds = get_str("FIREBASE_CREDENTIALS_B64", required=True)
        decode_firebase_credentials(b64_creds)
    except ValueError as e:
        errors.append(str(e))

    # Check PORT (Render sets PORT dynamically; fallback to 8080/10000)
    try:
        get_int("PORT", default=int(os.environ.get("PORT", "10000")), required=False)
    except ValueError as e:
        errors.append(str(e))

    if errors:
        logger.error("Configuration validation failed with the following errors:")
        for err in errors:
            logger.error(" - %s", err)
        raise SystemExit(1)

    logger.info("Configuration successfully validated for Telegram Bot.")


# Run validation upon loading module
validate_config()


@dataclass(frozen=True)
class Settings:
    """Immutable production settings container."""
    BOT_TOKEN: str = get_str("BOT_TOKEN")
    ADMIN_ID: int = get_int("ADMIN_ID")
    MAIN_CHANNEL_ID: int = get_int("MAIN_CHANNEL_ID")
    BACKUP_CHANNEL_ID: int = get_int("BACKUP_CHANNEL_ID")
    MAIN_CHANNEL_LINK: str = get_str("MAIN_CHANNEL_LINK")
    BACKUP_CHANNEL_LINK: str = get_str("BACKUP_CHANNEL_LINK")
    FIREBASE_CREDENTIALS_B64: str = get_str("FIREBASE_CREDENTIALS_B64")
    PORT: int = get_int("PORT", default=10000, required=False)
    
    @property
    def firebase_credentials_dict(self) -> Dict[str, Any]:
        """Returns decoded Firebase credentials dictionary."""
        return decode_firebase_credentials(self.FIREBASE_CREDENTIALS_B64)


# Singleton Config Instance
Config = Settings()

# Direct export of constants for flexible imports
BOT_TOKEN = Config.BOT_TOKEN
ADMIN_ID = Config.ADMIN_ID
MAIN_CHANNEL_ID = Config.MAIN_CHANNEL_ID
BACKUP_CHANNEL_ID = Config.BACKUP_CHANNEL_ID
MAIN_CHANNEL_LINK = Config.MAIN_CHANNEL_LINK
BACKUP_CHANNEL_LINK = Config.BACKUP_CHANNEL_LINK
FIREBASE_CREDENTIALS_B64 = Config.FIREBASE_CREDENTIALS_B64
PORT = Config.PORT


def initialize_firebase():
    """
    Helper function to initialize Firebase Admin SDK using the decoded credentials.
    Compatible with firebase-admin >=6.5.0
    """
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(Config.firebase_credentials_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully.")
        return firestore.client()
    except ImportError:
        logger.warning("firebase-admin package is not installed.")
        return None
    except Exception as e:
        logger.error("Failed to initialize Firebase Admin: %s", e)
        raise
