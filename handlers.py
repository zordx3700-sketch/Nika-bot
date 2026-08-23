# FILE: handlers.py
# CHANGE: Fixed category navigation flow, added 4-button menu + Request system, Series/Season/Episode flow, and ASCII styled URL page

"""
Production-Ready User Flow Handlers for Telegram Anime & Media Bot.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0

Complete USER Flow:
1. /start & Channel Membership:
   - Mandatory membership check on MAIN_CHANNEL_ID and BACKUP_CHANNEL_ID.
   - User registration in Firestore.
2. Home Menu (4 core buttons: Titles, Categories, Language, Help + 📩 Request button).
3. 📂 Categories:
   - Browse categories -> View titles inside category (does NOT redirect back to /start).
4. 🎬 Titles & 🌐 Languages browsing.
5. 🔍 Multi-Strategy Search & Suggestions (Title, Keywords, Aliases, Substrings).
6. 📺 Normal vs Series Flow:
   - Normal: Title -> Language -> Resolution -> URLs
   - Series: Title -> Season -> Episode -> Language -> Resolution -> URLs
7. 🔗 URL Page:
   - Premium formatted header box:
     ╭━━━━━━━━━━━━━━━━━━━━╮
            🎬 TITLE
     ╰━━━━━━━━━━━━━━━━━━━━╯
   - Multiple Watch & Download buttons opening external URLs directly.
8. 📩 Media Request System:
   - User submits request -> Saved in Firestore -> Forwarded to ADMIN_ID.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatMemberStatus, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import (
    ADMIN_ID,
    BACKUP_CHANNEL_ID,
    BACKUP_CHANNEL_LINK,
    MAIN_CHANNEL_ID,
    MAIN_CHANNEL_LINK,
)
from database import DatabaseManager
from keyboards import (
    cancel_action_keyboard,
    categories_keyboard,
    category_titles_keyboard,
    channel_links_keyboard,
    episodes_selection_keyboard,
    languages_browse_keyboard,
    languages_selection_keyboard,
    media_multi_urls_keyboard,
    resolutions_selection_keyboard,
    search_results_keyboard,
    seasons_selection_keyboard,
    titles_all_keyboard,
    user_main_menu_keyboard,
)

logger = logging.getLogger("UserHandlers")

# Shared database instance
db = DatabaseManager()

# Conversation states
STATE_USER_REQUEST_INPUT = 1


# =========================================================================
# MEMBERSHIP VERIFICATION
# =========================================================================

async def is_user_member(bot, user_id: int, channel_id: int) -> bool:
    """Check if user is a member of the required channel."""
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
        logger.warning("Membership check exception for %s in %s: %s", user_id, channel_id, e)
        return True


async def check_force_sub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Ensure user is subscribed to both MAIN and BACKUP channels."""
    user = update.effective_user
    if not user:
        return False

    is_main = await is_user_member(context.bot, user.id, MAIN_CHANNEL_ID)
    is_backup = await is_user_member(context.bot, user.id, BACKUP_CHANNEL_ID)

    if is_main and is_backup:
        return True

    msg_text = (
        "⚠️ *Channel Membership Required*\n\n"
        "To use this bot and access media links, please join our official updates and backup channels below.\n\n"
        "Tap the buttons to join, then tap **Verify Membership**."
    )
    markup = channel_links_keyboard(
        main_link=MAIN_CHANNEL_LINK,
        backup_link=BACKUP_CHANNEL_LINK,
        try_again_callback="chk_membership",
    )

    if update.callback_query:
        try:
            await update.callback_query.answer("⚠️ Please join both channels first!", show_alert=True)
            await update.callback_query.edit_message_text(
                text=msg_text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user.id, text=msg_text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN
            )
    elif update.message:
        await update.message.reply_text(
            text=msg_text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True
        )

    return False


# =========================================================================
# START COMMAND & HOME MENU
# =========================================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command, deep-linking, and registration."""
    user = update.effective_user
    if not user:
        return

    # Register user in Firestore
    db.register_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )

    # Check channel subscription
    if not await check_force_sub(update, context):
        return

    # Deep-linking check (e.g. /start t_XYZ)
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        if arg.startswith("t_"):
            title_id = arg.replace("t_", "")
            await show_title_entry(update, context, title_id)
            return

    text = (
        f"👋 Hello, *{user.first_name}*!\n\n"
        "🎬 *Welcome to Anime & Media Bot*\n"
        "Stream and download your favorite movies, web series, and anime with high-speed direct links.\n\n"
        "👇 *Select an option below or send any title name to search:*"
    )
    markup = user_main_menu_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display bot help guide."""
    if not await check_force_sub(update, context):
        return

    text = db.get_help_text()
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(text="🏠 Home", callback_data="nav_home")]])

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# CATEGORIES & TITLES BROWSING
# =========================================================================

async def user_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display paginated list of categories."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    data = query.data or "u_cats:1"
    page = 1
    if ":" in data:
        try:
            page = int(data.split(":")[1])
        except ValueError:
            page = 1

    cats = db.get_all_categories(only_enabled=True)
    if not cats:
        await query.edit_message_text(
            "📂 *Categories*\n\nNo categories available currently.",
            reply_markup=user_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    markup = categories_keyboard(cats, page=page, page_size=8)
    await query.edit_message_text(
        "📂 *Select a Category to Browse:*",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def user_category_titles_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show titles belonging ONLY to the selected category."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    # Format: ucat:<category_id>:<page>
    parts = query.data.split(":")
    cat_id = parts[1]
    page = int(parts[2]) if len(parts) >= 3 else 1

    cat_doc = db.get_category(cat_id)
    cat_name = cat_doc.get("name", "Category") if cat_doc else "Category"

    titles = db.get_titles_by_category(cat_id, only_published=True, limit=100)
    if not titles:
        text = f"📂 *Category:* `{cat_name}`\n\nNo titles available in this category yet."
        markup = category_titles_keyboard(cat_id, cat_name, [], page=1)
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        return

    text = f"📂 *Category:* `{cat_name}`\n\nSelect a title to view episodes/qualities:"
    markup = category_titles_keyboard(cat_id, cat_name, titles, page=page, page_size=8)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_titles_all_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all titles across categories."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    data = query.data or "u_titles:1"
    page = int(data.split(":")[1]) if ":" in data else 1

    titles = db.get_all_titles(only_published=True, limit=150)
    markup = titles_all_keyboard(titles, page=page, page_size=8)
    await query.edit_message_text(
        "🎬 *All Titles Library*\n\nSelect a title to browse options:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def user_languages_browse(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Browse by language."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    data = query.data or "u_langs:1"
    page = int(data.split(":")[1]) if ":" in data else 1

    langs = db.get_available_languages(only_enabled=True)
    markup = languages_browse_keyboard(langs, page=page, page_size=8)
    await query.edit_message_text(
        "🌐 *Browse by Audio / Language*\n\nSelect a language to discover available titles:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# =========================================================================
# SEARCH ENGINE
# =========================================================================

async def text_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text search queries with smart matching and suggestions."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user or not await check_force_sub(update, context):
        return

    query_text = update.message.text.strip()
    if query_text.startswith("/"):
        return

    results = db.search_titles(query_str=query_text, limit=10, user_id=user.id)

    if not results:
        text = (
            f"❌ *No results found for:* `{query_text}`\n\n"
            "• Please check spelling and try again.\n"
            "• Or tap **📩 Request** to request this title from admin!"
        )
        await update.message.reply_text(text=text, reply_markup=user_main_menu_keyboard(), parse_mode=ParseMode.MARKDOWN)
        return

    if len(results) == 1 and results[0].get("title_lower") == query_text.lower():
        await show_title_entry(update, context, results[0]["id"])
        return

    top_title = results[0].get("title", query_text)
    text = (
        f"🔍 *Search results for:* `{query_text}`\n\n"
        f"💡 *Did you mean:* **{top_title}**?\n\n"
        "Tap a title below to view:"
    )
    markup = search_results_keyboard(results)
    await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# TITLE / SERIES / SEASON / EPISODE / QUALITY FLOW
# =========================================================================

async def show_title_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, title_id: str) -> None:
    """Entry point when a title is selected (routes to Series flow or Normal flow)."""
    title_doc = db.get_title(title_id)
    if not title_doc or not title_doc.get("is_published", True):
        msg = "⚠️ This title is currently unavailable."
        if update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=user_main_menu_keyboard())
        elif update.message:
            await update.message.reply_text(msg, reply_markup=user_main_menu_keyboard())
        return

    title_name = title_doc.get("title", "Title")
    content_type = title_doc.get("content_type", "normal")

    if content_type == "series":
        # Series Flow -> Show Seasons
        seasons = db.get_seasons(title_id)
        if not seasons:
            text = (
                f"📺 *{title_name}*\n\n"
                "⚠️ *Seasons are being uploaded!*\n"
                "Please check back shortly or request via 📩 Request."
            )
            markup = user_main_menu_keyboard()
        else:
            text = f"📺 *{title_name}*\n\nSelect a season to view episodes:"
            markup = seasons_selection_keyboard(title_id, seasons, back_cb="nav_home")

        if update.callback_query:
            await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        elif update.message:
            await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    else:
        # Normal Flow -> Show Languages with Links
        combos = db.get_all_media_combos_for_title(title_id)
        valid_combos = [c for c in combos if c.get("watch_urls") or c.get("download_urls")]

        if not valid_combos:
            text = (
                f"🎬 *{title_name}*\n\n"
                "⚠️ *Links are being uploaded!*\n"
                "Please check back shortly or request via 📩 Request."
            )
            markup = user_main_menu_keyboard()
        else:
            available_langs = sorted(list({c.get("language", "") for c in valid_combos if c.get("language")}))
            text = f"🎬 *{title_name}*\n\n🗣️ *Select Audio / Language:*"
            markup = languages_selection_keyboard(available_langs, title_id=title_id, back_cb="nav_home")

        if update.callback_query:
            await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        elif update.message:
            await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_title_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for ut:<title_id>."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not await check_force_sub(update, context):
        return

    title_id = query.data.split(":")[1]
    await show_title_entry(update, context, title_id)


async def user_season_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for us_s:<title_id>:<season_id>."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]

    title_doc = db.get_title(title_id)
    season_doc = db.get_season(title_id, season_id)
    t_name = title_doc.get("title", "Series") if title_doc else "Series"
    s_name = season_doc.get("season_name", "Season") if season_doc else "Season"

    episodes = db.get_episodes(title_id, season_id)
    if not episodes:
        text = f"📺 *{t_name}* • `{s_name}`\n\n⚠️ No episodes uploaded in this season yet."
        markup = seasons_selection_keyboard(title_id, db.get_seasons(title_id), back_cb="nav_home")
    else:
        text = f"📺 *{t_name}* • `{s_name}`\n\nSelect an episode:"
        markup = episodes_selection_keyboard(title_id, season_id, episodes, back_cb=f"ut:{title_id}")

    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_episode_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for us_ep:<title_id>:<season_id>:<episode_id>."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    episode_id = parts[3]

    title_doc = db.get_title(title_id)
    season_doc = db.get_season(title_id, season_id)
    ep_doc = db.get_episode(title_id, season_id, episode_id)

    t_name = title_doc.get("title", "Series") if title_doc else "Series"
    s_name = season_doc.get("season_name", "Season") if season_doc else "Season"
    ep_name = ep_doc.get("episode_title", "Episode") if ep_doc else "Episode"

    combos = db.get_all_media_combos_for_title(title_id, season_id=season_id, episode_id=episode_id)
    valid_combos = [c for c in combos if c.get("watch_urls") or c.get("download_urls")]

    if not valid_combos:
        text = (
            f"📺 *{t_name}* • `{s_name}`\n"
            f"🎬 *{ep_name}*\n\n"
            "⚠️ Links are being uploaded for this episode! Please check back shortly."
        )
        markup = episodes_selection_keyboard(
            title_id, season_id, db.get_episodes(title_id, season_id), back_cb=f"ut:{title_id}"
        )
    else:
        available_langs = sorted(list({c.get("language", "") for c in valid_combos if c.get("language")}))
        text = (
            f"📺 *{t_name}* • `{s_name}`\n"
            f"🎬 *{ep_name}*\n\n"
            "🗣️ *Select Audio / Language:*"
        )
        markup = languages_selection_keyboard(
            available_langs,
            title_id=title_id,
            season_id=season_id,
            episode_id=episode_id,
            back_cb=f"us_s:{title_id}:{season_id}",
        )

    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_language_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback for ul:<title_id>:<lang> or ul:<title_id>:<season_id>:<episode_id>:<lang>."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    if len(parts) == 3:
        # Normal title: ul:<title_id>:<lang>
        title_id = parts[1]
        lang = parts[2]
        title_doc = db.get_title(title_id)
        t_name = title_doc.get("title", "Title") if title_doc else "Title"

        combos = db.get_all_media_combos_for_title(title_id)
        valid_res = [
            c.get("resolution", "")
            for c in combos
            if c.get("language", "").lower() == lang.lower() and (c.get("watch_urls") or c.get("download_urls"))
        ]
        text = f"🎬 *{t_name}*\n🌐 Language: `{lang}`\n\n🎞️ *Select Resolution / Quality:*"
        markup = resolutions_selection_keyboard(
            valid_res,
            title_id=title_id,
            language=lang,
            back_cb=f"ut:{title_id}",
        )
    else:
        # Series: ul:<title_id>:<season_id>:<episode_id>:<lang>
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]

        title_doc = db.get_title(title_id)
        season_doc = db.get_season(title_id, season_id)
        ep_doc = db.get_episode(title_id, season_id, episode_id)

        t_name = title_doc.get("title", "Series") if title_doc else "Series"
        s_name = season_doc.get("season_name", "Season") if season_doc else "Season"
        ep_name = ep_doc.get("episode_title", "Episode") if ep_doc else "Episode"

        combos = db.get_all_media_combos_for_title(title_id, season_id=season_id, episode_id=episode_id)
        valid_res = [
            c.get("resolution", "")
            for c in combos
            if c.get("language", "").lower() == lang.lower() and (c.get("watch_urls") or c.get("download_urls"))
        ]
        text = (
            f"📺 *{t_name}* • `{s_name}`\n"
            f"🎬 *{ep_name}*\n"
            f"🌐 Language: `{lang}`\n\n"
            "🎞️ *Select Resolution / Quality:*"
        )
        markup = resolutions_selection_keyboard(
            valid_res,
            title_id=title_id,
            language=lang,
            season_id=season_id,
            episode_id=episode_id,
            back_cb=f"us_ep:{title_id}:{season_id}:{episode_id}",
        )

    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_resolution_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display final URL page with bold box header and multiple Watch/Download buttons."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    if len(parts) == 4:
        # Normal title: ur:<title_id>:<lang>:<res>
        title_id = parts[1]
        lang = parts[2]
        res = parts[3]

        title_doc = db.get_title(title_id)
        t_name = title_doc.get("title", "Title").upper() if title_doc else "TITLE"

        combo = db.get_media_url_combo(title_id, language=lang, resolution=res) or {}
        w_urls = combo.get("watch_urls", [])
        dl_urls = combo.get("download_urls", [])
        w_labels = combo.get("watch_labels", [])
        dl_labels = combo.get("download_labels", [])

        # Beautiful Bold Box Title Header
        header_text = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            f"       🎬 {t_name}\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"🌐 *Language:* `{lang}`\n"
            f"🎞 *Quality:* `{res}`\n\n"
            "👇 *Tap a button below to open direct external link:*"
        )
        markup = media_multi_urls_keyboard(
            watch_urls=w_urls,
            download_urls=dl_urls,
            watch_labels=w_labels,
            download_labels=dl_labels,
            back_cb=f"ul:{title_id}:{lang}",
        )
    else:
        # Series: ur:<title_id>:<season_id>:<episode_id>:<lang>:<res>
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]
        res = parts[5]

        title_doc = db.get_title(title_id)
        season_doc = db.get_season(title_id, season_id)
        ep_doc = db.get_episode(title_id, season_id, episode_id)

        t_name = title_doc.get("title", "Series").upper() if title_doc else "SERIES"
        s_name = season_doc.get("season_name", "Season") if season_doc else "Season"
        ep_name = ep_doc.get("episode_title", "Episode") if ep_doc else "Episode"

        combo = db.get_media_url_combo(
            title_id, language=lang, resolution=res, season_id=season_id, episode_id=episode_id
        ) or {}
        w_urls = combo.get("watch_urls", [])
        dl_urls = combo.get("download_urls", [])
        w_labels = combo.get("watch_labels", [])
        dl_labels = combo.get("download_labels", [])

        header_text = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            f"       📺 {t_name}\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            f"📚 *{s_name}* • 🎬 *{ep_name}*\n"
            f"🌐 *Language:* `{lang}`\n"
            f"🎞 *Quality:* `{res}`\n\n"
            "👇 *Tap a button below to open direct external link:*"
        )
        markup = media_multi_urls_keyboard(
            watch_urls=w_urls,
            download_urls=dl_urls,
            watch_labels=w_labels,
            download_labels=dl_labels,
            back_cb=f"ul:{title_id}:{season_id}:{episode_id}:{lang}",
        )

    await query.edit_message_text(text=header_text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# USER REQUEST SYSTEM
# =========================================================================

async def start_user_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt user to send the media title they want to request."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()

    text = (
        "📩 *Request Missing Media*\n\n"
        "Please send the name of the Anime, Movie, or Web Series you would like to request:\n\n"
        "_Example: Solo Leveling Season 2, Oppenheimer, Jujutsu Kaisen_"
    )
    markup = cancel_action_keyboard("cancel_req")
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    return STATE_USER_REQUEST_INPUT


async def handle_user_request_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text input for request, save in Firestore, and notify Admin."""
    if not update.message or not update.message.text:
        return STATE_USER_REQUEST_INPUT

    user = update.effective_user
    req_text = update.message.text.strip()
    if not req_text or not user:
        return ConversationHandler.END

    # 1. Save to Firestore
    db.save_user_request(
        user_id=user.id,
        first_name=user.first_name or "User",
        username=user.username or "",
        request_text=req_text,
    )

    # 2. Forward notification to ADMIN_ID
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    admin_notify = (
        "📩 *NEW USER MEDIA REQUEST*\n\n"
        f"👤 *User:* {user.first_name} {user.last_name or ''} (@{user.username or 'None'})\n"
        f"🆔 *Telegram ID:* `{user.id}`\n"
        f"🎬 *Request:* `{req_text}`\n"
        f"⏰ *Time:* `{now_str}`"
    )
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notify,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logger.warning("Could not forward request to ADMIN_ID %s: %s", ADMIN_ID, e)

    # 3. Confirmation to user
    await update.message.reply_text(
        "✅ *Your request has been sent to the admin!*\n\n"
        "Thank you! We will review and upload it soon.",
        reply_markup=user_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def cancel_user_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel media request."""
    query = update.callback_query
    if query:
        await query.answer("Request cancelled.")
        await start_command(update, context)
    return ConversationHandler.END


# =========================================================================
# GLOBAL ERROR HANDLER
# =========================================================================

async def error_handler(update: Optional[object], context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error catcher."""
    logger.error("Exception in update: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ *An unexpected error occurred.* Please restart with /start.",
                reply_markup=user_main_menu_keyboard(),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            pass


# =========================================================================
# REGISTRATION
# =========================================================================

def register_user_handlers(app: Application) -> None:
    """Register all user flows and conversation handlers."""
    # Request ConversationHandler
    req_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_user_request, pattern="^u_request$")
        ],
        states={
            STATE_USER_REQUEST_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_request_input)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_user_request, pattern="^cancel_req$"),
            CommandHandler("cancel", cancel_user_request),
        ],
        per_chat=True,
    )
    app.add_handler(req_conv)

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Core Navigation & Verification callbacks
    app.add_handler(CallbackQueryHandler(start_command, pattern="^(nav_home|chk_membership)$"))
    app.add_handler(CallbackQueryHandler(help_command, pattern="^u_help$"))

    # Categories & Titles Callbacks
    app.add_handler(CallbackQueryHandler(user_categories_list, pattern="^u_cats"))
    app.add_handler(CallbackQueryHandler(user_category_titles_view, pattern="^ucat:"))
    app.add_handler(CallbackQueryHandler(user_titles_all_view, pattern="^u_titles:"))
    app.add_handler(CallbackQueryHandler(user_languages_browse, pattern="^u_langs:"))

    # Title & Series Hierarchy
    app.add_handler(CallbackQueryHandler(user_title_click, pattern="^ut:"))
    app.add_handler(CallbackQueryHandler(user_season_click, pattern="^us_s:"))
    app.add_handler(CallbackQueryHandler(user_episode_click, pattern="^us_ep:"))
    app.add_handler(CallbackQueryHandler(user_language_click, pattern="^ul:"))
    app.add_handler(CallbackQueryHandler(user_resolution_click, pattern="^ur:"))

    # Search query callback (filter by language)
    app.add_handler(
        CallbackQueryHandler(
            lambda u, c: text_search_handler(
                type("Obj", (object,), {"message": type("M", (object,), {"text": u.callback_query.data.split(":")[1]})()})(),
                c,
            ),
            pattern="^usrch_lang:",
        )
    )

    # Text Search fallback
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_search_handler))

    # Error handler
    app.add_error_handler(error_handler)
