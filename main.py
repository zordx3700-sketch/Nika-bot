"""
Production Main Entry Point for Telegram Bot on Render.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0
- Render Web Service (HTTP health check on PORT)

Features:
- Config validation
- Firebase Firestore initialization via DatabaseManager
- Background HTTP health check server returning "Anime Bot is running."
- Full registration of User and Admin handlers without circular dependencies
- Global unhandled exception logging & error handling
- Runs with app.run_polling(allowed_updates=Update.ALL_TYPES)
"""

import http.server
import logging
import os
import sys
import threading
from typing import Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

# Configuration and Database
from config import BOT_TOKEN, PORT, validate_config
from database import DatabaseManager

# Handlers
from admin import register_admin_handlers
from handlers import register_user_handlers, user_main_menu_keyboard

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Main")


# =========================================================================
# RENDER HTTP HEALTH CHECK SERVER
# =========================================================================

class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    """Simple HTTP request handler for Render health checks and keep-alive."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Anime Bot is running.")

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        # Suppress noisy health check access logs
        return


def start_health_server(port: int = 10000) -> None:
    """Start background HTTP server to satisfy Render Web Service port binding."""
    try:
        server_address = ("0.0.0.0", port)
        httpd = http.server.ThreadingHTTPServer(server_address, HealthCheckHandler)
        logger.info("HTTP Health Check Server listening on 0.0.0.0:%d", port)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
    except Exception as e:
        logger.error("Failed to start HTTP Health Server on port %d: %s", port, e)


# =========================================================================
# GLOBAL TELEGRAM ERROR HANDLER
# =========================================================================

async def global_error_handler(update: Optional[object], context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all unhandled error handler for telegram updates."""
    logger.error("Global exception caught: %s", context.error, exc_info=context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            err_msg = (
                "⚠️ *An error occurred while processing your request.*\n"
                "Please send /start to return to the main menu."
            )
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=err_msg,
                reply_markup=user_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as send_err:
            logger.warning("Could not send error notification message to user: %s", send_err)


# =========================================================================
# APPLICATION BOOTSTRAP
# =========================================================================

def main() -> None:
    """Initialize bot application and start polling."""
    logger.info("Initializing Telegram Media & Anime Bot...")

    # 1. Validate environment configuration
    validate_config()

    # 2. Initialize Firestore Database & Collections
    try:
        db = DatabaseManager()
        logger.info("Firebase Firestore database initialized successfully.")
    except Exception as e:
        logger.critical("Database initialization failed: %s", e, exc_info=True)
        sys.exit(1)

    # 3. Start Render HTTP Health Server in daemon thread
    bind_port = PORT or int(os.environ.get("PORT", 10000))
    start_health_server(bind_port)

    # 4. Build python-telegram-bot Application
    logger.info("Building Telegram Application (PTB >=22.0)...")
    app = Application.builder().token(BOT_TOKEN).build()

    # 5. Register Admin Handlers (ConversationHandlers & Callbacks)
    # Admin is registered first so priority conversation routes take precedence
    register_admin_handlers(app)
    logger.info("Admin handlers and ConversationHandler registered.")

    # 6. Register User Flow Handlers (Start, Search, Browse, URL selectors)
    register_user_handlers(app)
    logger.info("User flow handlers registered.")

    # 7. Register Global Error Handler
    app.add_error_handler(global_error_handler)

    # 8. Start Polling Loop
    logger.info("Bot is now starting polling with allowed_updates=Update.ALL_TYPES...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
