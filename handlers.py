"""
Production-Ready User Flow Handlers for Telegram Bot.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0

Complete USER flow:
1. /start & Deep-Linking / Verification:
   - Registers user in Firestore
   - Verifies channel membership on MAIN_CHANNEL_ID and BACKUP_CHANNEL_ID
   - If not joined: Shows Join Channel buttons with Verify & Continue
2. Navigation & Categories:
   - Category browser with pagination
   - Titles under category
3. Search & Smart Suggestions:
   - Text message search & /search command
   - Search suggestions: "Do you mean...?" with interactive title buttons
   - Logs searches to Firestore
4. Title & Media Selection Flow:
   - Select Title -> dynamically queries only available languages that have configured URLs
   - Select Language -> dynamically queries only available resolutions for that title+language
   - Select Resolution -> displays independent Watch (url=) and/or Download (url=) buttons
   - Pure redirection: Bot never downloads files itself.
5. Full error handling & graceful fallback notifications.
"""

import logging
from typing import Any, Dict, List, Optional

from telegram import Update
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    ADMIN_ID,
    BACKUP_CHANNEL_ID,
    BACKUP_CHANNEL_LINK,
    BOT_TOKEN,
    MAIN_CHANNEL_ID,
    MAIN_CHANNEL_LINK,
)
from database import DatabaseManager
from keyboards import (
    categories_keyboard,
    channel_links_keyboard,
    languages_selection_keyboard,
    media_actions_keyboard,
    resolutions_selection_keyboard,
    search_suggestions_keyboard,
    title_list_keyboard,
    user_help_keyboard,
    user_main_menu_keyboard,
)

logger = logging.getLogger("UserHandlers")

# Initialize shared database manager
db = DatabaseManager()


# =========================================================================
# CHANNEL MEMBERSHIP VERIFICATION
# =========================================================================

async def is_user_member(bot, user_id: int, channel_id: int) -> bool:
    """
    Check if the user is a member/administrator/creator in the given channel.
    Returns True if user is admin or if membership is verified.
    """
    if user_id == ADMIN_ID:
        return True

    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ]
    except Exception as e:
        logger.warning(
            "Could not check membership for user %s in channel %s: %s",
            user_id,
            channel_id,
            e,
        )
        # If bot lacks permissions or channel is misconfigured, avoid hard-locking users
        return True


async def check_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Verifies that the user has joined both MAIN and BACKUP channels.
    If not, responds with direct join links and returns False.
    """
    user = update.effective_user
    if not user:
        return False

    is_main_member = await is_user_member(context.bot, user.id, MAIN_CHANNEL_ID)
    is_backup_member = await is_user_member(context.bot, user.id, BACKUP_CHANNEL_ID)

    if is_main_member and is_backup_member:
        return True

    # User has not joined both channels
    msg_text = (
        "⚠️ *Channel Membership Required*\n\n"
        "To use this bot and access media links, please join our official updates and backup channels below.\n\n"
        "Click the buttons to join, then tap **Verify & Continue**."
    )
    reply_markup = channel_links_keyboard(
        main_link=MAIN_CHANNEL_LINK,
        backup_link=BACKUP_CHANNEL_LINK,
        try_again_callback="verify_sub",
    )

    if update.callback_query:
        try:
            await update.callback_query.answer(
                "⚠️ Please join both channels first!", show_alert=True
            )
            await update.callback_query.edit_message_text(
                text=msg_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user.id,
                text=msg_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN,
            )
    elif update.message:
        await update.message.reply_text(
            text=msg_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )

    return False


# =========================================================================
# START & MAIN MENU COMMANDS
# =========================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command, deep-linking, and registration."""
    user = update.effective_user
    if not user:
        return

    # 1. Register or update user in database
    db.register_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )

    # 2. Check channel membership
    if not await check_force_sub(update, context):
        return

    # 3. Check for deep linking arguments (e.g. /start t_XYZ)
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("t_"):
            title_id = arg.replace("t_", "")
            await show_title_details(update, context, title_id=title_id)
            return

    # 4. Display Main Menu
    welcome_text = (
        f"👋 Hello, *{user.first_name}*!\n\n"
        "🎬 *Welcome to the Media Bot*\n"
        "Find, stream, and download your favorite movies, series, and anime with instant high-speed direct links.\n\n"
        "👇 *Choose an option below or simply send any title to search:*"
    )
    reply_markup = user_main_menu_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.message:
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command and help button."""
    if not await check_force_sub(update, context):
        return

    help_text = db.get_help_text()
    reply_markup = user_help_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.message:
        await update.message.reply_text(
            text=help_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )


# =========================================================================
# CATEGORIES & BROWSING FLOW
# =========================================================================

async def categories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show paginated categories list."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Extract page from callback_data (e.g., u_cats:1)
    data = query.data or "u_cats:1"
    page = 1
    if ":" in data:
        try:
            page = int(data.split(":")[1])
        except ValueError:
            page = 1

    categories = db.get_all_categories(only_enabled=True)
    if not categories:
        await query.edit_message_text(
            "📂 *Categories*\n\nNo categories are available right now.",
            reply_markup=user_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = "📂 *Select a Category to Browse:*"
    reply_markup = categories_keyboard(categories, page=page, page_size=8)
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def category_titles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show titles under a selected category."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Format: ucat:<category_id>:<page>
    parts = (query.data or "").split(":")
    if len(parts) < 2:
        return

    cat_id = parts[1]
    page = 1
    if len(parts) >= 3:
        try:
            page = int(parts[2].replace("p", ""))
        except ValueError:
            page = 1

    category = db.get_category(cat_id)
    cat_name = category.get("name", "Category") if category else "Category"

    titles = db.get_titles_by_category(cat_id, limit=100)
    if not titles:
        text = f"📂 *Category:* {cat_name}\n\nNo titles found in this category yet."
        await query.edit_message_text(
            text=text,
            reply_markup=title_list_keyboard([], back_cb="u_cats:1"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"📂 *Category:* {cat_name}\n\nSelect a title to view available qualities & links:"
    reply_markup = title_list_keyboard(
        titles=titles,
        back_cb="u_cats:1",
        page=page,
        page_size=6,
        prefix="utitle",
    )
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# =========================================================================
# SEARCH & SUGGESTIONS FLOW
# =========================================================================

async def prompt_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompt user to type their search query."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    text = (
        "🔍 *Search Media Library*\n\n"
        "Send the title or name of the movie/series you want to watch.\n\n"
        "_Example: Naruto, Avengers, Spider-Man, Jujutsu Kaisen_"
    )
    await query.edit_message_text(
        text=text,
        reply_markup=user_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )


async def text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle natural text messages from users as search queries.
    Provides smart match suggestions (e.g. 'Do you mean...?')
    """
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    # Check force subscribe
    if not await check_force_sub(update, context):
        return

    search_query = update.message.text.strip()
    if search_query.startswith("/"):
        return  # Ignore unrecognized commands

    # Perform multi-strategy search with automatic logging
    results = db.search_titles(
        query_str=search_query,
        limit=10,
        user_id=user.id,
    )

    if not results:
        # No match found
        not_found_text = (
            f"❌ *No results found for:* `{search_query}`\n\n"
            "• Please check spelling and try again\n"
            "• Try using fewer keywords (e.g., 'Naruto' instead of 'Naruto Episode 1')\n"
            "• Browse categories from the main menu"
        )
        await update.message.reply_text(
            text=not_found_text,
            reply_markup=user_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # If single exact match is found with high confidence
    if len(results) == 1 and results[0].get("title_lower") == search_query.lower():
        title_id = results[0]["id"]
        await show_title_details(update, context, title_id=title_id)
        return

    # Multiple or partial results: "Do you mean...?" Suggestions
    top_title = results[0].get("title", search_query)
    suggestions_text = (
        f"🔍 *Results for:* `{search_query}`\n\n"
        f"💡 *Did you mean:* **{top_title}**?\n\n"
        "Select the exact title from the list below:"
    )
    reply_markup = search_suggestions_keyboard(results, query_text=search_query)

    await update.message.reply_text(
        text=suggestions_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# =========================================================================
# TITLE DETAILS & DYNAMIC MEDIA SELECTION FLOW
# =========================================================================

async def title_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle title selection from keyboard."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Format: utitle:<title_id>
    parts = (query.data or "").split(":")
    if len(parts) < 2:
        return

    title_id = parts[1]
    await show_title_details(update, context, title_id=title_id)


async def show_title_details(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    title_id: str,
    back_cb: str = "u_cats:1",
) -> None:
    """
    Display title overview and show ONLY the languages that have media URLs
    configured for this title.
    """
    title_data = db.get_title(title_id)
    if not title_data or not title_data.get("is_published", True):
        msg = "⚠️ This title is currently unavailable or has been removed."
        if update.callback_query:
            await update.callback_query.edit_message_text(
                msg, reply_markup=user_main_menu_keyboard()
            )
        elif update.message:
            await update.message.reply_text(
                msg, reply_markup=user_main_menu_keyboard()
            )
        return

    title_name = title_data.get("title", "Untitled")
    year = title_data.get("release_year")
    desc = title_data.get("description", "")

    # Query all media URL combinations for this title
    media_items = db.get_media_urls_for_title(title_id)
    
    # Filter only items that have at least watch_url or download_url
    valid_media = [
        m for m in media_items
        if (m.get("watch_url") and m.get("watch_url").strip())
        or (m.get("download_url") and m.get("download_url").strip())
    ]

    if not valid_media:
        no_links_text = (
            f"🎬 *{title_name}*" + (f" ({year})" if year else "") + "\n\n"
            f"{desc}\n\n"
            "⚠️ *Links coming soon!*\nNo active watch or download links are available for this title yet."
        )
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=no_links_text,
                reply_markup=title_list_keyboard([], back_cb=back_cb),
                parse_mode=ParseMode.MARKDOWN,
            )
        elif update.message:
            await update.message.reply_text(
                text=no_links_text,
                reply_markup=title_list_keyboard([], back_cb=back_cb),
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    # Extract distinct languages that actually have configured URLs
    available_langs: List[str] = []
    for item in valid_media:
        l_name = item.get("language", "").strip()
        if l_name and l_name not in available_langs:
            available_langs.append(l_name)

    caption = (
        f"🎬 *{title_name}*" + (f" ({year})" if year else "") + "\n\n"
        + (f"📝 _{desc}_\n\n" if desc else "")
        + "🗣️ *Step 1/2: Select Audio / Language:*"
    )

    reply_markup = languages_selection_keyboard(
        languages=available_langs,
        title_id=title_id,
        back_cb=back_cb,
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.message:
        await update.message.reply_text(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN,
        )


async def language_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle language selection for a title.
    Show ONLY the resolutions that have URLs configured for this title + language.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Format: ulang:<title_id>:<language>
    parts = (query.data or "").split(":")
    if len(parts) < 3:
        return

    title_id = parts[1]
    selected_language = parts[2]

    title_data = db.get_title(title_id)
    title_name = title_data.get("title", "Title") if title_data else "Title"

    # Query all media URL combinations for this title
    media_items = db.get_media_urls_for_title(title_id)

    # Filter items matching selected language that have valid URLs
    valid_resols: List[str] = []
    for m in media_items:
        if m.get("language", "").strip().lower() == selected_language.strip().lower():
            if (m.get("watch_url") and m.get("watch_url").strip()) or (
                m.get("download_url") and m.get("download_url").strip()
            ):
                r_name = m.get("resolution", "").strip()
                if r_name and r_name not in valid_resols:
                    valid_resols.append(r_name)

    if not valid_resols:
        await query.edit_message_text(
            f"🎬 *{title_name}*\n\n⚠️ No resolutions found for language *{selected_language}*.",
            reply_markup=languages_selection_keyboard([], title_id=title_id),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = (
        f"🎬 *{title_name}*\n"
        f"🗣️ *Language:* `{selected_language}`\n\n"
        "📺 *Step 2/2: Select Quality / Resolution:*"
    )
    reply_markup = resolutions_selection_keyboard(
        resolutions=valid_resols,
        title_id=title_id,
        language=selected_language,
        back_cb=f"utitle:{title_id}",
    )

    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def resolution_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle resolution selection.
    Fetch and display the independent Watch and Download buttons with direct external URLs.
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Format: ures:<title_id>:<language>:<resolution>
    parts = (query.data or "").split(":")
    if len(parts) < 4:
        return

    title_id = parts[1]
    language = parts[2]
    resolution = parts[3]

    title_data = db.get_title(title_id)
    title_name = title_data.get("title", "Media") if title_data else "Media"

    media = db.get_media_url(title_id, language=language, resolution=resolution)
    if not media:
        await query.edit_message_text(
            "⚠️ The requested link combination is no longer available.",
            reply_markup=user_main_menu_keyboard(),
        )
        return

    watch_url = (media.get("watch_url") or "").strip()
    download_url = (media.get("download_url") or "").strip()
    file_size = media.get("file_size", "").strip()
    extra_note = media.get("extra_note", "").strip()

    text_parts = [
        f"🍿 *{title_name}*",
        f"🗣️ *Language:* {language}",
        f"📺 *Quality:* {resolution}",
    ]
    if file_size:
        text_parts.append(f"📦 *File Size:* {file_size}")
    if extra_note:
        text_parts.append(f"ℹ️ *Note:* {extra_note}")

    text_parts.append("\n🚀 *Your links are ready! Tap a button below to open:*")
    final_text = "\n".join(text_parts)

    reply_markup = media_actions_keyboard(
        watch_url=watch_url,
        download_url=download_url,
        back_cb=f"ulang:{title_id}:{language}",
    )

    await query.edit_message_text(
        text=final_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# =========================================================================
# NAVIGATION & COMMON CALLBACKS
# =========================================================================

async def verify_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback when user clicks 'Verify & Continue'."""
    query = update.callback_query
    if not query:
        return

    user = update.effective_user
    if not user:
        return

    is_main = await is_user_member(context.bot, user.id, MAIN_CHANNEL_ID)
    is_backup = await is_user_member(context.bot, user.id, BACKUP_CHANNEL_ID)

    if is_main and is_backup:
        await query.answer("✅ Verification successful!", show_alert=True)
        await start_command(update, context)
    else:
        await query.answer(
            "❌ You have not joined both channels yet. Please join and try again.",
            show_alert=True,
        )


async def nav_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to main menu."""
    await start_command(update, context)


async def noop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Empty callback handler for static page badges."""
    if update.callback_query:
        await update.callback_query.answer()


# =========================================================================
# GLOBAL ERROR HANDLER
# =========================================================================

async def error_handler(update: Optional[object], context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and notify user gracefully."""
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)

    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ *An unexpected error occurred.* Please try again with /start.",
                reply_markup=user_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


# =========================================================================
# HANDLER REGISTRATION
# =========================================================================

def register_user_handlers(app: Application) -> None:
    """Register all user-facing command, message, and callback handlers."""
    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", prompt_search_callback))

    # Navigation & Verification callbacks
    app.add_handler(CallbackQueryHandler(verify_sub_callback, pattern="^verify_sub$"))
    app.add_handler(CallbackQueryHandler(nav_home_callback, pattern="^nav_home$"))
    app.add_handler(CallbackQueryHandler(noop_callback, pattern="^noop$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^u_help$"))

    # Categories & Browsing callbacks
    app.add_handler(CallbackQueryHandler(categories_callback, pattern="^u_cats"))
    app.add_handler(CallbackQueryHandler(category_titles_callback, pattern="^ucat:"))

    # Search callbacks
    app.add_handler(CallbackQueryHandler(prompt_search_callback, pattern="^u_search$"))

    # Title & Media Selection callbacks
    app.add_handler(CallbackQueryHandler(title_detail_callback, pattern="^utitle:"))
    app.add_handler(CallbackQueryHandler(language_select_callback, pattern="^ulang:"))
    app.add_handler(CallbackQueryHandler(resolution_select_callback, pattern="^ures:"))

    # Natural text message search handler
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_search_handler)
    )

    # Error handler
    app.add_error_handler(error_handler)
