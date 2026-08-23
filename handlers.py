# FILE: handlers.py
# CHANGE: Implemented strict User Flow (Categories, Help, Request), Series (Season -> Episode -> Lang -> Reg -> Links) & Normal (Lang -> Reg -> Links) navigation, and User Requests

"""
User-Facing Message and Callback Handlers for Telegram Anime & Media Bot.

Compatible with:
- python-telegram-bot: >=22.0, <23.0

Features:
- Mandatory channel membership verification
- Strict User Home (Categories, Help, Request)
- Category-scoped Title exploration
- Normal Title Flow: Category -> Title -> Language -> Regulation -> Links/Buttons
- Series Title Flow: Category -> Title -> Season -> Episode -> Language -> Regulation -> Links/Buttons
- Only shows Languages & Regulations that actually have configured links in database
- Dynamic multi-button URL rendering (Download, Watch, Telegram, Server 2, etc.)
- Deep search engine matching titles and keywords
- Interactive Anime / Media Request flow for users
"""

import logging
from typing import Optional

from telegram import Update
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

from config import ADMIN_ID, BACKUP_CHANNEL_ID, BACKUP_CHANNEL_LINK, MAIN_CHANNEL_ID, MAIN_CHANNEL_LINK
from database import DatabaseManager
from keyboards import (
    cancel_action_keyboard,
    categories_keyboard,
    category_titles_keyboard,
    channel_links_keyboard,
    episodes_selection_keyboard,
    home_button,
    search_results_keyboard,
    seasons_selection_keyboard,
    user_languages_keyboard,
    user_main_menu_keyboard,
    user_media_links_keyboard,
    user_regulations_keyboard,
)

logger = logging.getLogger("UserHandlers")
db = DatabaseManager()

# Conversation states for User Request
STATE_USER_REQUEST = 101


# =========================================================================
# MEMBERSHIP VERIFICATION
# =========================================================================

async def check_user_membership(bot, user_id: int) -> bool:
    """Verify if user is a member of configured mandatory public channels."""
    channels = [MAIN_CHANNEL_ID, BACKUP_CHANNEL_ID]
    allowed_statuses = [
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ]

    for ch_id in channels:
        if not ch_id:
            continue
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status not in allowed_statuses:
                return False
        except Exception as e:
            logger.warning("Membership check failed for %s on channel %s: %s", user_id, ch_id, e)
            # If channel permissions prevent checking, do not block user
            continue
    return True


async def require_membership_or_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Helper to verify membership and prompt user with join buttons if needed."""
    user = update.effective_user
    if not user:
        return False

    # Skip check for bot admin
    if ADMIN_ID and user.id == ADMIN_ID:
        return True

    is_member = await check_user_membership(context.bot, user.id)
    if is_member:
        return True

    text = (
        "👋 *Welcome to Anime & Media Bot!*\n\n"
        "To use this bot and access unlimited streaming & downloads, "
        "please join our official channels below and tap **Verify Membership**:"
    )
    markup = channel_links_keyboard(MAIN_CHANNEL_LINK, BACKUP_CHANNEL_LINK)

    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

    return False


# =========================================================================
# USER COMMANDS & HOME
# =========================================================================

async def user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command. Registers user and opens home menu."""
    user = update.effective_user
    if not user:
        return

    db.register_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        language_code=user.language_code,
    )

    if not await require_membership_or_prompt(update, context):
        return

    welcome_text = (
        f"👋 *Welcome, {user.first_name}!* 🎬\n\n"
        "Find and stream your favorite **Anime, Movies & Web Series** in high quality.\n\n"
        "• Tap **📂 Categories** to browse titles\n"
        "• Or simply **type any movie/anime name** to search instantly!"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=welcome_text,
            reply_markup=user_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.message:
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=user_main_menu_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )


async def user_verify_membership_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback query to re-check channel membership."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user = update.effective_user
    if not user:
        return

    is_member = await check_user_membership(context.bot, user.id)
    if is_member or (ADMIN_ID and user.id == ADMIN_ID):
        await query.answer("✅ Membership verified! Welcome!", show_alert=True)
        await user_start(update, context)
    else:
        await query.answer("❌ You haven't joined both channels yet. Please join and try again.", show_alert=True)


async def user_home_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to User home screen."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    await user_start(update, context)


async def user_help_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display bot help guide."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    help_text = db.get_help_text()
    from keyboards import InlineKeyboardMarkup
    markup = InlineKeyboardMarkup([[home_button()]])

    await query.edit_message_text(
        text=help_text,
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# =========================================================================
# CATEGORIES & TITLE LISTING FLOW
# =========================================================================

async def user_categories_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display paginated list of enabled categories."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

    cats = db.get_all_categories(only_enabled=True)
    if not cats:
        from keyboards import InlineKeyboardMarkup
        await query.edit_message_text(
            "📂 *No Categories Available Yet.*\nPlease check back later or send /start.",
            reply_markup=InlineKeyboardMarkup([[home_button()]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = "📂 *Select a Category to Browse Titles:*"
    markup = categories_keyboard(cats, page=page)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_category_titles_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display published titles for the selected category."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    cat_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    category = db.get_category(cat_id)
    cat_name = category.get("name", "Category") if category else "Category"

    titles = db.get_titles_by_category(category_id=cat_id, only_published=True)
    if not titles:
        from keyboards import InlineKeyboardMarkup, back_button
        await query.edit_message_text(
            f"📂 *Category: {cat_name}*\n\n⚠️ No titles available in this category yet.",
            reply_markup=InlineKeyboardMarkup([
                [back_button("u_cats:1", label="⬅️ Categories"), home_button()]
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"📂 *Category: {cat_name}*\n\nSelect a title to view streaming & download links:"
    markup = category_titles_keyboard(category_id=cat_id, category_name=cat_name, titles=titles, page=page)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# TITLE SELECTION -> (SERIES or NORMAL) FLOW
# =========================================================================

async def user_title_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle click on a Title button.
    - If Series: Shows Seasons -> Episodes -> Language -> Regulation -> Links
    - If Normal: Shows Language -> Regulation -> Links
    """
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    title = db.get_title(title_id)
    if not title:
        await query.answer("⚠️ Title not found or removed.", show_alert=True)
        return

    t_name = title.get("title", "Title")
    c_type = title.get("content_type", "normal")
    desc = title.get("description", "")
    desc_str = f"\n\n_{desc}_" if desc else ""

    # 1. SERIES FLOW
    if c_type == "series":
        seasons = db.get_seasons(title_id)
        if not seasons:
            from keyboards import InlineKeyboardMarkup, back_button
            back_cb = f"ucat:{cat_id}:1" if cat_id else "u_cats:1"
            await query.edit_message_text(
                f"📺 *{t_name}*{desc_str}\n\n⚠️ No seasons available yet for this series.",
                reply_markup=InlineKeyboardMarkup([[back_button(back_cb), home_button()]]),
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        text = f"📺 *{t_name}* (Series){desc_str}\n\nSelect a **Season**:"
        markup = seasons_selection_keyboard(title_id=title_id, seasons=seasons, category_id=cat_id)
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
        return

    # 2. NORMAL (MOVIE / SINGLE) FLOW -> Show Languages
    languages = db.get_languages_for_content(title_id=title_id, only_with_links=True)
    if not languages:
        from keyboards import InlineKeyboardMarkup, back_button
        back_cb = f"ucat:{cat_id}:1" if cat_id else "u_cats:1"
        await query.edit_message_text(
            f"🎬 *{t_name}*{desc_str}\n\n⚠️ No download/watch links available yet for this title.",
            reply_markup=InlineKeyboardMarkup([[back_button(back_cb), home_button()]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"🎬 *{t_name}*{desc_str}\n\n🗣️ Select **Audio / Language**:"
    markup = user_languages_keyboard(
        languages=languages,
        title_id=title_id,
        category_id=cat_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# SERIES: SEASON & EPISODE SELECTION
# =========================================================================

async def user_season_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User selected a Season for a series -> Show Episodes."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    cat_id = parts[3] if len(parts) > 3 else ""

    title = db.get_title(title_id)
    season = db.get_season(title_id, season_id)
    t_name = title.get("title", "Series") if title else "Series"
    s_name = season.get("season_name", "Season") if season else "Season"

    episodes = db.get_episodes(title_id, season_id)
    if not episodes:
        from keyboards import InlineKeyboardMarkup, back_button
        await query.edit_message_text(
            f"📺 *{t_name}* ➔ *{s_name}*\n\n⚠️ No episodes available in this season yet.",
            reply_markup=InlineKeyboardMarkup([
                [back_button(f"ut:{title_id}:{cat_id}", label="⬅️ Seasons"), home_button()]
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"📺 *{t_name}* ➔ *{s_name}*\n\nSelect an **Episode**:"
    markup = episodes_selection_keyboard(
        title_id=title_id,
        season_id=season_id,
        episodes=episodes,
        category_id=cat_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def user_episode_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User selected an Episode in a Series -> Show Languages for this episode."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    episode_id = parts[3]
    cat_id = parts[4] if len(parts) > 4 else ""

    title = db.get_title(title_id)
    season = db.get_season(title_id, season_id)
    episode = db.get_episode(title_id, season_id, episode_id)

    t_name = title.get("title", "Series") if title else "Series"
    s_name = season.get("season_name", "Season") if season else "Season"
    ep_name = episode.get("episode_title", "Episode") if episode else "Episode"

    languages = db.get_languages_for_content(
        title_id=title_id,
        season_id=season_id,
        episode_id=episode_id,
        only_with_links=True,
    )

    if not languages:
        from keyboards import InlineKeyboardMarkup, back_button
        await query.edit_message_text(
            f"📺 *{t_name}* ➔ *{s_name}* ➔ *{ep_name}*\n\n⚠️ No streaming/download links available yet for this episode.",
            reply_markup=InlineKeyboardMarkup([
                [back_button(f"us_s:{title_id}:{season_id}:{cat_id}", label="⬅️ Episodes"), home_button()]
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"📺 *{t_name}* ➔ *{s_name}* ➔ *{ep_name}*\n\n🗣️ Select **Audio / Language**:"
    markup = user_languages_keyboard(
        languages=languages,
        title_id=title_id,
        category_id=cat_id,
        season_id=season_id,
        episode_id=episode_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# LANGUAGE SELECTION -> SHOW REGULATIONS
# =========================================================================

async def user_language_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User selected Language -> Show available Regulations under that language."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    is_series = parts[0] == "u_l_ep"

    if is_series:
        # u_l_ep:title_id:season_id:episode_id:language:category_id
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        language = parts[4]
        cat_id = parts[5] if len(parts) > 5 else ""

        title = db.get_title(title_id)
        season = db.get_season(title_id, season_id)
        episode = db.get_episode(title_id, season_id, episode_id)
        header = f"📺 *{title.get('title', 'Series')}* ➔ *{season.get('season_name', 'Season')}* ➔ *{episode.get('episode_title', 'Episode')}*"

        regulations = db.get_regulations_for_content(
            title_id=title_id,
            language=language,
            season_id=season_id,
            episode_id=episode_id,
            only_with_links=True,
        )
    else:
        # u_l_t:title_id:language:category_id
        title_id = parts[1]
        language = parts[2]
        cat_id = parts[3] if len(parts) > 3 else ""
        season_id, episode_id = None, None

        title = db.get_title(title_id)
        header = f"🎬 *{title.get('title', 'Title')}*"

        regulations = db.get_regulations_for_content(
            title_id=title_id,
            language=language,
            only_with_links=True,
        )

    if not regulations:
        from keyboards import InlineKeyboardMarkup, back_button
        back_cb = f"us_ep:{title_id}:{season_id}:{episode_id}:{cat_id}" if is_series else f"ut:{title_id}:{cat_id}"
        await query.edit_message_text(
            f"{header}\nLanguage: `{language}`\n\n⚠️ No regulations available for this language.",
            reply_markup=InlineKeyboardMarkup([[back_button(back_cb), home_button()]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = f"{header}\n🗣️ Language: *{language}*\n\n🎞️ Select **Quality / Regulation**:"
    markup = user_regulations_keyboard(
        regulations=regulations,
        title_id=title_id,
        language=language,
        category_id=cat_id,
        season_id=season_id,
        episode_id=episode_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# REGULATION SELECTION -> RENDER FINAL URL BUTTONS
# =========================================================================

async def user_regulation_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User selected Regulation -> Render all configured external action links/buttons."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    is_series = parts[0] == "u_r_ep"

    if is_series:
        # u_r_ep:title_id:season_id:episode_id:language:regulation:category_id
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        language = parts[4]
        regulation = parts[5]
        cat_id = parts[6] if len(parts) > 6 else ""

        title = db.get_title(title_id)
        season = db.get_season(title_id, season_id)
        episode = db.get_episode(title_id, season_id, episode_id)
        header = f"📺 *{title.get('title', 'Series')}*\n• *{season.get('season_name', 'Season')}* ➔ *{episode.get('episode_title', 'Episode')}*"
        back_cb = f"u_l_ep:{title_id}:{season_id}:{episode_id}:{language}:{cat_id}"

        links = db.get_links_for_content(
            title_id=title_id,
            language=language,
            regulation=regulation,
            season_id=season_id,
            episode_id=episode_id,
        )
    else:
        # u_r_t:title_id:language:regulation:category_id
        title_id = parts[1]
        language = parts[2]
        regulation = parts[3]
        cat_id = parts[4] if len(parts) > 4 else ""

        title = db.get_title(title_id)
        header = f"🎬 *{title.get('title', 'Movie')}*"
        back_cb = f"u_l_t:{title_id}:{language}:{cat_id}"

        links = db.get_links_for_content(
            title_id=title_id,
            language=language,
            regulation=regulation,
        )

    if not links:
        from keyboards import InlineKeyboardMarkup, back_button
        await query.edit_message_text(
            f"{header}\nLanguage: `{language}` | Quality: `{regulation}`\n\n⚠️ No direct links found.",
            reply_markup=InlineKeyboardMarkup([[back_button(back_cb), home_button()]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = (
        f"{header}\n"
        f"🗣️ *Language:* `{language}`\n"
        f"🎞️ *Regulation / Quality:* `{regulation}`\n\n"
        f"✨ Tap below to watch or download:"
    )
    markup = user_media_links_keyboard(links=links, back_cb=back_cb)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# SEARCH ENGINE HANDLER
# =========================================================================

async def user_text_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle regular text messages from user as instant media search."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if text.startswith("/"):
        return

    user = update.effective_user
    if not user:
        return

    if not await require_membership_or_prompt(update, context):
        return

    results = db.search_titles(query_str=text, user_id=user.id, limit=10)
    if not results:
        from keyboards import InlineKeyboardMarkup
        await update.message.reply_text(
            f"🔍 *Search Results for:* `{text}`\n\n"
            "❌ No matching anime or movies found.\n\n"
            "• Check for spelling errors\n"
            "• Or tap **📩 Request** below to request it from admins!",
            reply_markup=InlineKeyboardMarkup([
                [
                    user_main_menu_keyboard().inline_keyboard[0][0],  # Categories
                ],
                [
                    user_main_menu_keyboard().inline_keyboard[1][1],  # Request
                    home_button(),
                ]
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    reply_text = f"🔍 *Found {len(results)} results for:* `{text}`\n\nSelect a title to view:"
    markup = search_results_keyboard(results)
    await update.message.reply_text(text=reply_text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# USER MEDIA REQUEST CONVERSATION
# =========================================================================

async def start_user_request_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Initiate user media request conversation."""
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            "📩 *Request Anime or Movie*\n\n"
            "Please send the **name, release year, or link** of the anime/movie you want us to add:\n\n"
            "_(Type your message or tap Cancel below)_",
            reply_markup=cancel_action_keyboard(callback_data="nav_home"),
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.message:
        await update.message.reply_text(
            "📩 *Request Anime or Movie*\n\n"
            "Please send the **name, release year, or link** of the anime/movie you want us to add:\n\n"
            "_(Type your message or tap Cancel below)_",
            reply_markup=cancel_action_keyboard(callback_data="nav_home"),
            parse_mode=ParseMode.MARKDOWN,
        )
    return STATE_USER_REQUEST


async def handle_user_request_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive and save user request, notify admin."""
    user = update.effective_user
    if not user or not update.message or not update.message.text:
        return ConversationHandler.END

    req_text = update.message.text.strip()
    db.add_user_request(
        user_id=user.id,
        username=user.username or user.first_name,
        request_text=req_text,
    )

    # Forward alert to admin if configured
    if ADMIN_ID:
        try:
            admin_msg = (
                f"🔔 *New Media Request Received!*\n\n"
                f"• User: {user.mention_markdown()} (`{user.id}`)\n"
                f"• Request: `{req_text}`"
            )
            await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.warning("Could not forward request notification to admin %s: %s", ADMIN_ID, e)

    await update.message.reply_text(
        "✅ *Thank You! Your request has been submitted to admins.*\n"
        "We will add it as soon as possible!",
        reply_markup=user_main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def cancel_user_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel media request conversation."""
    query = update.callback_query
    if query:
        await query.answer("Request cancelled.")
        await user_start(update, context)
    return ConversationHandler.END


# =========================================================================
# HANDLER REGISTRATION
# =========================================================================

def register_user_handlers(app: Application) -> None:
    """Register all user commands and interactive callbacks."""

    # 1. User Request Conversation
    req_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_user_request_prompt, pattern=r"^u_request$"),
            CommandHandler("request", start_user_request_prompt),
        ],
        states={
            STATE_USER_REQUEST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_request_input),
            ]
        },
        fallbacks=[
            CallbackQueryHandler(cancel_user_request, pattern=r"^nav_home$"),
            CommandHandler("cancel", cancel_user_request),
        ],
        allow_reentry=True,
    )
    app.add_handler(req_conv)

    # 2. Commands & Home Navigation
    app.add_handler(CommandHandler("start", user_start))
    app.add_handler(CommandHandler("help", user_help_callback))
    app.add_handler(CallbackQueryHandler(user_verify_membership_callback, pattern=r"^chk_membership$"))
    app.add_handler(CallbackQueryHandler(user_home_callback, pattern=r"^nav_home$"))
    app.add_handler(CallbackQueryHandler(user_help_callback, pattern=r"^u_help$"))

    # 3. Categories & Titles Browsing
    app.add_handler(CallbackQueryHandler(user_categories_list_callback, pattern=r"^u_cats:\d+$"))
    app.add_handler(CallbackQueryHandler(user_category_titles_callback, pattern=r"^ucat:.+:\d+$"))

    # 4. Title & Series Selection
    app.add_handler(CallbackQueryHandler(user_title_click, pattern=r"^ut:[^:]+.*$"))
    app.add_handler(CallbackQueryHandler(user_season_click, pattern=r"^us_s:[^:]+:[^:]+.*$"))
    app.add_handler(CallbackQueryHandler(user_episode_click, pattern=r"^us_ep:[^:]+:[^:]+:[^:]+.*$"))

    # 5. Language & Regulation Selectors
    app.add_handler(CallbackQueryHandler(user_language_click, pattern=r"^(u_l_t|u_l_ep):.+$"))
    app.add_handler(CallbackQueryHandler(user_regulation_click, pattern=r"^(u_r_t|u_r_ep):.+$"))

    # 6. Global Text Search
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_text_search))
