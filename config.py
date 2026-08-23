import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_str_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely retrieve a string environment variable.
    Strips leading/trailing whitespace if the value exists.
    """
    value = os.getenv(key)
    if value is not None:
        value = value.strip()
    return value if value else default


def get_int_env(key: str, default: Optional[int] = None) -> Optional[int]:
    """
    Safely retrieve and parse an integer environment variable.
    Returns the default value if the key is missing or invalid.
    """
    value = get_str_env(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(
            f"Environment variable '{key}' with value '{value}' could not be parsed as an integer. "
            f"Falling back to default: {default}"
        )
        return default


def parse_admin_ids(key: str = "ADMIN_ID") -> List[int]:
    """
    Parses ADMIN_ID environment variable into a list of integers.
    Supports comma-separated integers (e.g., "123456,789012") or a single integer.
    """
    raw_val = get_str_env(key, "")
    if not raw_val:
        return []

    admin_list = []
    for part in raw_val.split(","):
        part = part.strip()
        if part:
            try:
                admin_list.append(int(part))
            except ValueError:
                logger.warning(f"Invalid admin ID entry '{part}' in {key}. Skipping.")
    return admin_list


def parse_firebase_credentials(key: str = "FIREBASE_CREDENTIALS_B64") -> Optional[Dict[str, Any]]:
    """
    Safely decodes Base64 encoded Firebase service account credentials
    and parses them into a dictionary.
    """
    b64_string = get_str_env(key)
    if not b64_string:
        return None

    try:
        decoded_bytes = base64.b64decode(b64_string)
        decoded_str = decoded_bytes.decode("utf-8")
        return json.loads(decoded_str)
    except Exception as e:
        logger.error(f"Failed to decode or parse {key}: {e}")
        return None


# Environment Variables Initialization
BOT_TOKEN: str = get_str_env("BOT_TOKEN", "")
ADMIN_IDS: List[int] = parse_admin_ids("ADMIN_ID")
PRIMARY_ADMIN_ID: Optional[int] = ADMIN_IDS[0] if ADMIN_IDS else None

MAIN_CHANNEL_ID: Optional[int] = get_int_env("MAIN_CHANNEL_ID")
BACKUP_CHANNEL_ID: Optional[int] = get_int_env("BACKUP_CHANNEL_ID")

MAIN_CHANNEL_LINK: str = get_str_env("MAIN_CHANNEL_LINK", "")
BACKUP_CHANNEL_LINK: str = get_str_env("BACKUP_CHANNEL_LINK", "")

FIREBASE_CREDENTIALS_B64: str = get_str_env("FIREBASE_CREDENTIALS_B64", "")
FIREBASE_CREDENTIALS_DICT: Optional[Dict[str, Any]] = parse_firebase_credentials("FIREBASE_CREDENTIALS_B64")

# Port assignment suitable for hosting environments like Render
PORT: int = get_int_env("PORT", 10000)


def validate_config() -> bool:
    """
    Validates required configuration variables.
    Logs explicit error messages for missing or invalid parameters.
    Returns True if valid, raises ValueError if essential configuration is missing.
    """
    errors = []

    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is missing or empty.")

    if not ADMIN_IDS:
        errors.append("ADMIN_ID is missing or contains no valid integer IDs.")

    if MAIN_CHANNEL_ID is None:
        errors.append("MAIN_CHANNEL_ID is missing or not a valid integer.")

    if BACKUP_CHANNEL_ID is None:
        errors.append("BACKUP_CHANNEL_ID is missing or not a valid integer.")

    if not MAIN_CHANNEL_LINK:
        errors.append("MAIN_CHANNEL_LINK is missing or empty.")

    if not BACKUP_CHANNEL_LINK:
        errors.append("BACKUP_CHANNEL_LINK is missing or empty.")

    if not FIREBASE_CREDENTIALS_B64:
        errors.append("FIREBASE_CREDENTIALS_B64 is missing or empty.")
    elif FIREBASE_CREDENTIALS_DICT is None:
        errors.append("FIREBASE_CREDENTIALS_B64 is invalid, corrupted, or failed Base64/JSON parsing.")

    if errors:
        error_msg = "Configuration validation failed:\n - " + "\n - ".join(errors)
        logger.critical(error_msg)
        raise ValueError(error_msg)

    logger.info("Configuration successfully validated.")
    return True
