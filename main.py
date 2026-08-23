import os
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.error import (
    TelegramError,
    Forbidden,
    BadRequest,
    RetryAfter,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

from config import (
    BOT_TOKEN,
    ADMIN_ID,
    MAIN_CHANNEL_ID,
    BACKUP_CHANNEL_ID,
    MAIN_CHANNEL_LINK,
    BACKUP_CHANNEL_LINK,
    POSTER_CHANNEL_ID,
    QUALITY_CHANNELS,
    AVAILABLE_QUALITIES,
    AVAILABLE_LANGUAGES,
    validate_config,
)

from database import DatabaseManager


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    format=(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger("anime_bot")


# =====================================================
# RENDER HEALTH SERVER
# =====================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain",
        )
        self.end_headers()
        self.wfile.write(
            b"Anime Bot is running."
        )

    def log_message(self, format, *args):
        return


def run_health_server():
    port = int(
        os.getenv("PORT", "8080")
    )

    try:
        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler,
        )

        logger.info(
            "Health server running on port %s",
            port,
        )

        server.serve_forever()

    except Exception:
        logger.exception(
            "Health server stopped."
        )


# =====================================================
# MEMBERSHIP
# =====================================================

async def check_membership(
    bot,
    user_id: int,
) -> bool:

    try:
        main = await bot.get_chat_member(
            MAIN_CHANNEL_ID,
            user_id,
        )

        backup = await bot.get_chat_member(
            BACKUP_CHANNEL_ID,
            user_id,
        )

        valid = {
            "member",
            "administrator",
            "creator",
        }

        return (
            main.status in valid
            and backup.status in valid
        )

    except TelegramError as e:
        logger.warning(
            "Membership check failed: %s",
            e,
        )
        return False


# =====================================================
# KEYBOARDS
# =====================================================

def join_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Main Channel",
                url=MAIN_CHANNEL_LINK,
            )
        ],
        [
            InlineKeyboardButton(
                "📢 Backup Channel",
                url=BACKUP_CHANNEL_LINK,
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Check Membership",
                callback_data="verify",
            )
        ],
    ])


def main_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔎 Search Anime",
                callback_data="search",
            ),
        ],
        [
            InlineKeyboardButton(
                "📂 Anime List",
                callback_data="list_0",
            ),
            InlineKeyboardButton(
                "👤 My Details",
                callback_data="my",
            ),
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            ),
        ],
    ])


def start_text(user):

    name = user.first_name or "User"

    return (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       🎬 ANIME HUB\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"Welcome, <b>{name}</b>! 👋\n\n"
        "Search your favorite Anime and "
        "choose Season, Quality, Language "
        "and Episode.\n\n"
        "✨ Premium Anime Experience"
    )


# =====================================================
# START
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user

    DatabaseManager.register_user(user)

    if not await check_membership(
        context.bot,
        user.id,
    ):

        text = (
            "╭━━━━━━━━━━━━━━━━━━━━╮\n"
            "       🔐 ACCESS REQUIRED\n"
            "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
            "Please join both official channels "
            "to continue using Anime Hub."
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                text,
                reply_markup=join_keyboard(),
            )
        else:
            await update.message.reply_text(
                text,
                reply_markup=join_keyboard(),
            )

        return

    if update.callback_query:
        await update.callback_query.edit_message_text(
            start_text(user),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )
    else:
        await update.message.reply_text(
            start_text(user),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )


# =====================================================
# SEARCH
# =====================================================

async def ask_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query

    await query.answer()

    await query.message.reply_text(
        "🔎 <b>Search Anime</b>\n\n"
        "Send the Anime name or keyword:",
        parse_mode=ParseMode.HTML,
    )

    context.user_data["waiting_search"] = True


async def handle_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    user = update.effective_user

    if not await check_membership(
        context.bot,
        user.id,
    ):
        await start(update, context)
        return

    text = update.message.text.strip()

    # Admin conversation takes priority
    if context.user_data.get("admin_state"):
        return

    DatabaseManager.register_user(user)

    anime, suggestions = (
        DatabaseManager.search_anime(text)
    )

    DatabaseManager.add_search_history(
        user.id,
        text,
        anime["name"] if anime else None,
    )

    context.user_data["waiting_search"] = False

    if not anime:

        if suggestions:

            buttons = [
                [
                    InlineKeyboardButton(
                        f"🎬 {name}",
                        callback_data=(
                            "suggest:" +
                            str(index)
                        ),
                    )
                ]
                for index, name in enumerate(
                    suggestions
                )
            ]

            context.user_data[
                "suggestions"
            ] = suggestions

            buttons.append([
                InlineKeyboardButton(
                    "🔎 Search Again",
                    callback_data="search",
                )
            ])

            text_msg = (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "      ❌ NOT FOUND\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                "Maybe you meant:"
            )

            await update.message.reply_text(
                text_msg,
                reply_markup=InlineKeyboardMarkup(
                    buttons
                ),
            )

        else:

            await update.message.reply_text(
                "❌ Anime not found.\n\n"
                "Try another Anime name.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔎 Search Again",
                            callback_data="search",
                        )
                    ]
                ]),
            )

        return

    await show_anime(
        update,
        context,
        anime,
    )


# =====================================================
# ANIME PROFILE
# =====================================================

async def show_anime(
    update,
    context,
    anime,
):

    context.user_data[
        "current_anime_id"
    ] = anime["id"]

    context.user_data[
        "current_anime"
    ] = anime

    poster_message_id = anime.get(
        "poster_message_id"
    )

    if (
        poster_message_id
        and POSTER_CHANNEL_ID
    ):

        try:
            await context.bot.copy_message(
                chat_id=update.effective_user.id,
                from_chat_id=POSTER_CHANNEL_ID,
                message_id=int(
                    poster_message_id
                ),
            )
        except TelegramError:
            logger.warning(
                "Could not copy poster."
            )

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        f"      🎬 {anime['name']}\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"⭐ Rating: {anime.get('rating', 'N/A')}/10\n"
        f"📚 Seasons: {anime.get('season_count', 1)}\n\n"
        "Choose a Season:"
    )

    seasons = anime.get(
        "season_count",
        1,
    )

    buttons = []

    for season in range(
        1,
        seasons + 1,
    ):

        buttons.append([
            InlineKeyboardButton(
                f"📚 Season {season}",
                callback_data=f"season:{season}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🔎 Search",
            callback_data="search",
        ),
        InlineKeyboardButton(
            "🔄 Start",
            callback_data="start",
        ),
    ])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =====================================================
# QUALITY
# =====================================================

async def show_quality(
    query,
    context,
    season: int,
):

    anime_id = context.user_data.get(
        "current_anime_id"
    )

    if not anime_id:
        await query.answer(
            "Session expired. Search again.",
            show_alert=True,
        )
        return

    qualities = (
        DatabaseManager
        .get_available_qualities(
            anime_id,
            season,
        )
    )

    if not qualities:

        await query.answer(
            "No quality is available.",
            show_alert=True,
        )
        return

    buttons = []

    row = []

    for quality in qualities:

        row.append(
            InlineKeyboardButton(
                f"🎞 {quality}",
                callback_data=(
                    f"quality:{quality}"
                ),
            )
        )

        if len(row) == 3:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data="back_anime",
        ),
    ])

    await query.edit_message_text(
        "🎞 <b>Select Quality</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =====================================================
# LANGUAGE
# =====================================================

async def show_languages(
    query,
    context,
    quality: str,
):

    anime_id = context.user_data[
        "current_anime_id"
    ]

    season = context.user_data[
        "current_season"
    ]

    languages = (
        DatabaseManager
        .get_available_languages(
            anime_id,
            season,
            quality,
        )
    )

    if not languages:

        await query.answer(
            "No language is available.",
            show_alert=True,
        )
        return

    buttons = []

    for language in languages:

        icon = (
            "🇮🇳"
            if language == "Hindi"
            else "🇬🇧"
        )

        buttons.append([
            InlineKeyboardButton(
                f"{icon} {language}",
                callback_data=(
                    f"lang:{language}"
                ),
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Back",
            callback_data=f"season:"
            f"{season}",
        )
    ])

    await query.edit_message_text(
        (
            "🌐 <b>Select Language</b>\n\n"
            f"Quality: <b>{quality}</b>"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =====================================================
# EPISODE LIST
# =====================================================

EPISODES_PER_PAGE = 8


async def show_episodes(
    query,
    context,
    page: int = 0,
):

    anime_id = context.user_data[
        "current_anime_id"
    ]

    season = context.user_data[
        "current_season"
    ]

    quality = context.user_data[
        "current_quality"
    ]

    language = context.user_data[
        "current_language"
    ]

    count = (
        DatabaseManager
        .get_episode_count(
            anime_id,
            season,
            quality,
            language,
        )
    )

    if count <= 0:

        await query.edit_message_text(
            "❌ No episodes are available "
            "for this selection."
        )
        return

    context.user_data[
        "episode_page"
    ] = page

    start = page * EPISODES_PER_PAGE + 1

    end = min(
        start + EPISODES_PER_PAGE - 1,
        count,
    )

    buttons = []

    row = []

    for ep in range(start, end + 1):

        row.append(
            InlineKeyboardButton(
                f"Episode {ep:02d}",
                callback_data=f"episode:{ep}",
            )
        )

        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"episodes:{page - 1}",
            )
        )

    if end < count:
        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"episodes:{page + 1}",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            "🔎 Search",
            callback_data="search",
        ),
        InlineKeyboardButton(
            "🔄 Start",
            callback_data="start",
        ),
    ])

    anime = context.user_data[
        "current_anime"
    ]

    text = (
        f"🎬 <b>{anime['name']}</b>\n"
        f"📚 Season {season}\n"
        f"🎞 {quality} • 🌐 {language}\n\n"
        f"<b>Episodes {start}–{end}</b>"
    )

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =====================================================
# EPISODE OPEN
# =====================================================

async def open_episode(
    query,
    context,
    episode: int,
):

    anime = context.user_data.get(
        "current_anime"
    )

    anime_id = context.user_data[
        "current_anime_id"
    ]

    season = context.user_data[
        "current_season"
    ]

    quality = context.user_data[
        "current_quality"
    ]

    language = context.user_data[
        "current_language"
    ]

    mapping = (
        DatabaseManager
        .get_episode_mapping(
            anime_id,
            season,
            episode,
            quality,
            language,
        )
    )

    if not mapping:

        await query.answer(
            "Episode is not available.",
            show_alert=True,
        )
        return

    user_id = query.from_user.id

    previous = context.user_data.get(
        "last_episode_message_id"
    )

    if previous:

        try:
            await context.bot.delete_message(
                chat_id=user_id,
                message_id=previous,
            )
        except TelegramError:
            pass

    try:

        copied = await context.bot.copy_message(
            chat_id=user_id,
            from_chat_id=int(
                mapping["channel_id"]
            ),
            message_id=int(
                mapping["message_id"]
            ),
        )

        context.user_data[
            "last_episode_message_id"
        ] = copied.message_id

    except TelegramError as e:

        logger.error(
            "Episode copy failed: %s",
            e,
        )

        await query.answer(
            "Unable to load this episode.",
            show_alert=True,
        )

        return

    DatabaseManager.add_episode_history(
        user_id,
        anime["name"],
        season,
        episode,
        quality,
        language,
    )

    await query.answer(
        f"Episode {episode} loaded."
    )

    # Navigation message
    buttons = []

    if episode > 1:
        buttons.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=(
                    f"episode:"
                    f"{episode - 1}"
                ),
            )
        )

    buttons.append(
        InlineKeyboardButton(
            "📋 Episodes",
            callback_data=(
                f"episodes:"
                f"{context.user_data.get('episode_page', 0)}"
            ),
        )
    )

    if episode < (
        DatabaseManager.get_episode_count(
            anime_id,
            season,
            quality,
            language,
        )
    ):
        buttons.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=(
                    f"episode:"
                    f"{episode + 1}"
                ),
            )
        )

    await query.message.reply_text(
        (
            f"🎬 <b>{anime['name']}</b>\n"
            f"📚 Season {season}\n"
            f"🎞 Episode {episode}\n"
            f"📺 {quality} • {language}"
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            buttons,
            [
                InlineKeyboardButton(
                    "🔎 Search",
                    callback_data="search",
                ),
                InlineKeyboardButton(
                    "🔄 Start",
                    callback_data="start",
                ),
            ],
        ]),
    )


# =====================================================
# MY DETAILS
# =====================================================

async def show_my_details(
    query,
    context,
):

    user = DatabaseManager.get_user(
        query.from_user.id
    )

    if not user:

        await query.answer(
            "No user information found.",
            show_alert=True,
        )
        return

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "        👤 MY DETAILS\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👤 Name: "
        f"{user.get('first_name', '')}\n"
        f"🔗 Username: "
        f"@{user.get('username', '') if user.get('username') else 'N/A'}\n"
        f"🆔 Telegram ID: "
        f"{user.get('telegram_id')}\n\n"
        f"🔎 Total Searches: "
        f"{user.get('total_searches', 0)}\n"
        f"🎬 Episodes Opened: "
        f"{user.get('total_episode_opens', 0)}"
    )

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔎 Search History",
                    callback_data="history_search",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🎬 Episode History",
                    callback_data="history_episode",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Main Menu",
                    callback_data="start",
                ),
            ],
        ]),
    )


async def show_search_history(
    query,
    context,
):

    data = DatabaseManager.get_search_history(
        query.from_user.id
    )

    if not data:

        text = "🔎 No search history yet."

    else:

        lines = [
            "🔎 <b>Search History</b>\n"
        ]

        for item in data[:20]:

            anime = (
                item.get("anime_name")
                or "Not Found"
            )

            keyword = item.get(
                "keyword",
                "",
            )

            lines.append(
                f"• <b>{keyword}</b> → {anime}"
            )

        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⬅️ My Details",
                    callback_data="my",
                )
            ]
        ]),
    )


async def show_episode_history(
    query,
    context,
):

    data = DatabaseManager.get_episode_history(
        query.from_user.id
    )

    if not data:

        text = "🎬 No episode history yet."

    else:

        lines = [
            "🎬 <b>Episode History</b>\n"
        ]

        for item in data[:30]:

            lines.append(
                f"• {item.get('anime_name')} "
                f"S{item.get('season')} "
                f"E{item.get('episode')} "
                f"({item.get('quality')} "
                f"{item.get('language')})"
            )

        text = "\n".join(lines)

    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "⬅️ My Details",
                    callback_data="my",
                )
            ]
        ]),
    )


# =====================================================
# ANIME LIST
# =====================================================

async def show_anime_list(
    query,
    page: int = 0,
):

    animes = DatabaseManager.get_all_animes()

    if not animes:

        await query.edit_message_text(
            "📂 Anime List is empty.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="start",
                    )
                ]
            ]),
        )

        return

    per_page = 8

    start = page * per_page
    end = start + per_page

    current = animes[start:end]

    buttons = []

    for anime in current:

        buttons.append([
            InlineKeyboardButton(
                f"🎬 {anime['name']}",
                callback_data=(
                    f"listanime:{anime['id']}"
                ),
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                "⬅️ Previous",
                callback_data=f"list:{page - 1}",
            )
        )

    if end < len(animes):
        navigation.append(
            InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"list:{page + 1}",
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            "⬅️ Main Menu",
            callback_data="start",
        )
    ])

    await query.edit_message_text(
        "📂 <b>Available Anime</b>\n\n"
        "Select an Anime:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            buttons
        ),
    )


# =====================================================
# ADMIN
# =====================================================

def is_admin(user_id: int):
    return user_id == ADMIN_ID


async def admin_panel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(
        update.effective_user.id
    ):
        await update.message.reply_text(
            "⛔ Access denied."
        )
        return

    total = DatabaseManager.get_total_users()

    text = (
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "       🛠 ADMIN PANEL\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"👥 Total Users: <b>{total}</b>\n\n"
        "Choose an action:"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕ Add Anime",
                callback_data="admin:add",
            ),
        ],
        [
            InlineKeyboardButton(
                "🎞 Add Episode",
                callback_data="admin:episode",
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Edit Anime",
                callback_data="admin:edit",
            ),
            InlineKeyboardButton(
                "🗑 Delete Anime",
                callback_data="admin:delete",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔑 Keywords",
                callback_data="admin:keywords",
            ),
        ],
        [
            InlineKeyboardButton(
                "👥 Users",
                callback_data="admin:users",
            ),
        ],
        [
            InlineKeyboardButton(
                "ℹ️ Edit Help",
                callback_data="admin:help",
            ),
        ],
    ]

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            keyboard
        ),
    )


# =====================================================
# ADMIN ADD ANIME CONVERSATION
# =====================================================

(
    A_NAME,
    A_POSTER,
    A_RATING,
    A_SEASONS,
    A_EPISODES,
    A_KEYWORDS,
) = range(6)


async def admin_add_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(
        update.effective_user.id
    ):
        return ConversationHandler.END

    await update.callback_query.answer()

    context.user_data[
        "admin_state"
    ] = "add_anime"

    await update.callback_query.message.reply_text(
        "➕ <b>Add Anime</b>\n\n"
        "Send Anime name:",
        parse_mode=ParseMode.HTML,
    )

    return A_NAME


async def admin_add_name(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data[
        "add_name"
    ] = update.message.text.strip()

    await update.message.reply_text(
        "Send Poster Message ID.\n\n"
        "The poster must exist in POSTER_CHANNEL_ID."
    )

    return A_POSTER


async def admin_add_poster(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:
        poster = int(
            update.message.text.strip()
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Message ID must be a number."
        )
        return A_POSTER

    context.user_data[
        "add_poster"
    ] = poster

    await update.message.reply_text(
        "Send Rating.\n\n"
        "Example: 8.5"
    )

    return A_RATING


async def admin_add_rating(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:
        rating = float(
            update.message.text.strip()
        )

        if not 0 <= rating <= 10:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ Rating must be between 0 and 10."
        )

        return A_RATING

    context.user_data[
        "add_rating"
    ] = rating

    await update.message.reply_text(
        "How many Seasons?\n\n"
        "Example: 3"
    )

    return A_SEASONS


async def admin_add_seasons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        seasons = int(
            update.message.text.strip()
        )

        if seasons < 1 or seasons > 100:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ Enter a valid season count."
        )

        return A_SEASONS

    context.user_data[
        "add_seasons"
    ] = seasons

    await update.message.reply_text(
        "Send episode count for each season.\n\n"
        "Example for 3 seasons:\n"
        "12,24,13"
    )

    return A_EPISODES


async def admin_add_episodes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    raw = update.message.text.strip()

    try:

        values = [
            int(x.strip())
            for x in raw.split(",")
        ]

        seasons = context.user_data[
            "add_seasons"
        ]

        if len(values) != seasons:
            raise ValueError

        if any(x < 1 for x in values):
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ Enter exactly one episode "
            "count for each season.\n\n"
            "Example:\n"
            "12,24,13"
        )

        return A_EPISODES

    context.user_data[
        "add_episode_counts"
    ] = values

    await update.message.reply_text(
        "Enter search keywords/aliases separated "
        "by commas.\n\n"
        "Example:\n"
        "naruto,naruto anime,nrt"
    )

    return A_KEYWORDS


async def admin_add_keywords(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    keywords = [
        x.strip()
        for x in update.message.text.split(",")
        if x.strip()
    ]

    try:

        anime_id = DatabaseManager.add_anime(
            name=context.user_data[
                "add_name"
            ],
            rating=context.user_data[
                "add_rating"
            ],
            poster_message_id=context.user_data[
                "add_poster"
            ],
            season_count=context.user_data[
                "add_seasons"
            ],
            episodes_per_season=context.user_data[
                "add_episode_counts"
            ],
            keywords=keywords,
        )

    except ValueError as e:

        await update.message.reply_text(
            f"❌ {e}"
        )

        context.user_data.pop(
            "admin_state",
            None,
        )

        return ConversationHandler.END

    context.user_data.pop(
        "admin_state",
        None,
    )

    await update.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "      ✅ ANIME ADDED\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"🎬 {context.user_data.get('add_name')}\n\n"
        f"Anime ID:\n<code>{anime_id}</code>\n\n"
        "Now use <b>🎞 Add Episode</b> "
        "to map every Episode's Telegram "
        "Message ID.",
        parse_mode=ParseMode.HTML,
    )

    return ConversationHandler.END


async def cancel_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    context.user_data.pop(
        "admin_state",
        None,
    )

    await update.message.reply_text(
        "❌ Operation cancelled."
    )

    return ConversationHandler.END


# =====================================================
# ADMIN ADD EPISODE CONVERSATION
# =====================================================

(
    E_ANIME,
    E_SEASON,
    E_QUALITY,
    E_LANGUAGE,
    E_MAPPING,
) = range(6, 11)


async def admin_episode_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not is_admin(
        update.effective_user.id
    ):
        return ConversationHandler.END

    await update.callback_query.answer()

    context.user_data[
        "admin_state"
    ] = "add_episode"

    await update.callback_query.message.reply_text(
        "🎞 <b>Add Episode</b>\n\n"
        "Send the Anime ID or the exact "
        "Anime name.\n\n"
        "(Anime ID was shown when the "
        "Anime was added, or open it from "
        "📂 Anime List.)\n\n"
        "Send /cancel to stop anytime.",
        parse_mode=ParseMode.HTML,
    )

    return E_ANIME


async def admin_episode_anime(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    raw = update.message.text.strip()

    anime = DatabaseManager.get_anime(raw)

    if not anime:
        anime, _ = DatabaseManager.search_anime(raw)

    if not anime:

        await update.message.reply_text(
            "❌ Anime not found.\n\n"
            "Send a valid Anime ID or name, "
            "or /cancel to stop."
        )

        return E_ANIME

    context.user_data["ep_anime_id"] = anime["id"]
    context.user_data["ep_anime_name"] = anime["name"]
    context.user_data["ep_season_count"] = (
        anime.get("season_count", 1)
    )

    await update.message.reply_text(
        f"🎬 <b>{anime['name']}</b>\n"
        f"📚 Total Seasons: "
        f"{anime.get('season_count', 1)}\n\n"
        "Send the Season number:",
        parse_mode=ParseMode.HTML,
    )

    return E_SEASON


async def admin_episode_season(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    try:

        season = int(
            update.message.text.strip()
        )

        season_count = context.user_data[
            "ep_season_count"
        ]

        if season < 1 or season > season_count:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ Enter a valid Season number "
            "(1 to "
            f"{context.user_data['ep_season_count']})."
        )

        return E_SEASON

    context.user_data["ep_season"] = season

    await update.message.reply_text(
        "Send Quality.\n\n"
        "Available: "
        + ", ".join(AVAILABLE_QUALITIES)
    )

    return E_QUALITY


async def admin_episode_quality(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    quality = update.message.text.strip()

    if quality not in AVAILABLE_QUALITIES:

        await update.message.reply_text(
            "❌ Invalid Quality.\n\n"
            "Choose one of: "
            + ", ".join(AVAILABLE_QUALITIES)
        )

        return E_QUALITY

    context.user_data["ep_quality"] = quality

    await update.message.reply_text(
        "Send Language.\n\n"
        "Available: "
        + ", ".join(AVAILABLE_LANGUAGES)
    )

    return E_LANGUAGE


async def admin_episode_language(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    language = update.message.text.strip()

    if language not in AVAILABLE_LANGUAGES:

        await update.message.reply_text(
            "❌ Invalid Language.\n\n"
            "Choose one of: "
            + ", ".join(AVAILABLE_LANGUAGES)
        )

        return E_LANGUAGE

    quality = context.user_data["ep_quality"]

    channel_id = QUALITY_CHANNELS.get(
        (quality, language)
    )

    if not channel_id:

        await update.message.reply_text(
            "❌ No channel is configured for "
            f"{quality} + {language}.\n\n"
            "Check the CHANNEL_* environment "
            "variables and try again.\n\n"
            "Operation cancelled."
        )

        context.user_data.pop("admin_state", None)

        return ConversationHandler.END

    context.user_data["ep_language"] = language
    context.user_data["ep_channel_id"] = channel_id

    anime_name = context.user_data["ep_anime_name"]
    season = context.user_data["ep_season"]

    await update.message.reply_text(
        f"🎬 <b>{anime_name}</b> — S{season} — "
        f"{quality} — {language}\n\n"
        "Now send episodes one by one in this "
        "format:\n\n"
        "<code>episode_number,message_id</code>\n\n"
        "Example:\n"
        "<code>1,4821</code>\n\n"
        "The Message ID must be the ID of that "
        "episode's message inside the source "
        "channel for this Quality + Language.\n\n"
        "Send /done when finished, or /cancel "
        "to stop.",
        parse_mode=ParseMode.HTML,
    )

    return E_MAPPING


async def admin_episode_mapping(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    raw = update.message.text.strip()

    parts = raw.split(",")

    if len(parts) != 2:

        await update.message.reply_text(
            "❌ Send in format:\n"
            "<code>episode_number,message_id</code>\n\n"
            "Or /done to finish.",
            parse_mode=ParseMode.HTML,
        )

        return E_MAPPING

    try:

        episode = int(parts[0].strip())
        message_id = int(parts[1].strip())

        if episode < 1 or message_id < 1:
            raise ValueError

    except ValueError:

        await update.message.reply_text(
            "❌ Both Episode number and Message "
            "ID must be positive numbers.\n\n"
            "Example:\n"
            "<code>1,4821</code>",
            parse_mode=ParseMode.HTML,
        )

        return E_MAPPING

    DatabaseManager.save_episode_mapping(
        anime_id=context.user_data["ep_anime_id"],
        season=context.user_data["ep_season"],
        episode=episode,
        quality=context.user_data["ep_quality"],
        language=context.user_data["ep_language"],
        channel_id=context.user_data["ep_channel_id"],
        message_id=message_id,
    )

    await update.message.reply_text(
        f"✅ Episode {episode} saved.\n\n"
        "Send the next "
        "<code>episode_number,message_id</code>, "
        "or /done to finish.",
        parse_mode=ParseMode.HTML,
    )

    return E_MAPPING


async def admin_episode_done(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    anime_name = context.user_data.get(
        "ep_anime_name", ""
    )

    season = context.user_data.get("ep_season")
    quality = context.user_data.get("ep_quality")
    language = context.user_data.get("ep_language")

    for key in list(context.user_data.keys()):
        if key.startswith("ep_"):
            context.user_data.pop(key, None)

    context.user_data.pop("admin_state", None)

    await update.message.reply_text(
        "╭━━━━━━━━━━━━━━━━━━━━╮\n"
        "     ✅ EPISODES SAVED\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
        f"🎬 {anime_name}\n"
        f"📚 Season {season}\n"
        f"🎞 {quality} • 🌐 {language}\n\n"
        "Use 🎞 Add Episode again to add more "
        "Quality/Language combinations for "
        "this Anime."
    )

    return ConversationHandler.END


# =====================================================
# CALLBACK ROUTER
# =====================================================

async def callbacks(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    query = update.callback_query
    data = query.data

    await query.answer()

    user_id = query.from_user.id

    # -------------------------------------------------
    # Membership verification
    # -------------------------------------------------

    if data == "verify":

        if await check_membership(
            context.bot,
            user_id,
        ):

            await query.edit_message_text(
                start_text(query.from_user),
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu(),
            )

        else:

            await query.edit_message_text(
                "❌ You have not joined both "
                "channels yet.\n\n"
                "Join both channels and try again.",
                reply_markup=join_keyboard(),
            )

        return

    # -------------------------------------------------
    # Start
    # -------------------------------------------------

    if data == "start":

        if not await check_membership(
            context.bot,
            user_id,
        ):
            await query.edit_message_text(
                "🔐 Please join both channels first.",
                reply_markup=join_keyboard(),
            )
            return

        context.user_data.clear()

        await query.edit_message_text(
            start_text(query.from_user),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(),
        )

        return

    # -------------------------------------------------
    # Protected callbacks
    # -------------------------------------------------

    if not await check_membership(
        context.bot,
        user_id,
    ):

        await query.edit_message_text(
            "🔐 Please join both channels first.",
            reply_markup=join_keyboard(),
        )

        return

    # -------------------------------------------------
    # Search
    # -------------------------------------------------

    if data == "search":

        context.user_data[
            "waiting_search"
        ] = True

        await query.edit_message_text(
            "🔎 <b>Search Anime</b>\n\n"
            "Send the Anime name or keyword:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔄 Cancel",
                        callback_data="start",
                    )
                ]
            ]),
        )

        return

    # -------------------------------------------------
    # Help
    # -------------------------------------------------

    if data == "help":

        help_text = (
            DatabaseManager.get_help()
        )

        await query.edit_message_text(
            (
                "╭━━━━━━━━━━━━━━━━━━━━╮\n"
                "        ℹ️ HELP\n"
                "╰━━━━━━━━━━━━━━━━━━━━╯\n\n"
                f"{help_text}"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ Main Menu",
                        callback_data="start",
                    )
                ]
            ]),
        )

        return

    # -------------------------------------------------
    # My Details
    # -------------------------------------------------

    if data == "my":

        await show_my_details(
            query,
            context,
        )

        return

    if data == "history_search":

        await show_search_history(
            query,
            context,
        )

        return

    if data == "history_episode":

        await show_episode_history(
            query,
            context,
        )

        return

    # -------------------------------------------------
    # Anime List
    # -------------------------------------------------

    if data.startswith("list_"):

        page = int(
            data.split("_")[1]
        )

        await show_anime_list(
            query,
            page,
        )

        return

    if data.startswith("listanime:"):

        anime_id = data.split(
            ":",
            1,
        )[1]

        anime = DatabaseManager.get_anime(
            anime_id
        )

        if not anime:

            await query.answer(
                "Anime not found.",
                show_alert=True,
            )

            return

        context.user_data[
            "current_anime_id"
        ] = anime_id

        context.user_data[
            "current_anime"
        ] = anime

        seasons = anime.get(
            "season_count",
            1,
        )

        buttons = [
            [
                InlineKeyboardButton(
                    f"📚 Season {s}",
                    callback_data=f"season:{s}",
                )
            ]
            for s in range(
                1,
                seasons + 1,
            )
        ]

        buttons.append([
            InlineKeyboardButton(
                "⬅️ Anime List",
                callback_data="list:0",
            )
        ])

        await query.edit_message_text(
            (
                f"🎬 <b>{anime['name']}</b>\n\n"
                f"⭐ Rating: "
                f"{anime.get('rating', 'N/A')}/10\n"
                f"📚 Seasons: {seasons}\n\n"
                "Select Season:"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return

    # -------------------------------------------------
    # Suggestions
    # -------------------------------------------------

    if data.startswith("suggest:"):

        index = int(
            data.split(":")[1]
        )

        suggestions = context.user_data.get(
            "suggestions",
            [],
        )

        if index >= len(suggestions):
            return

        anime, _ = (
            DatabaseManager.search_anime(
                suggestions[index]
            )
        )

        if anime:

            # Send profile as a fresh message
            await query.message.reply_text(
                (
                    f"🎬 <b>{anime['name']}</b>\n\n"
                    f"⭐ Rating: "
                    f"{anime.get('rating', 'N/A')}/10\n"
                    f"📚 Seasons: "
                    f"{anime.get('season_count', 1)}"
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "▶️ Select",
                            callback_data=(
                                f"listanime:{anime['id']}"
                            ),
                        )
                    ]
                ]),
            )

        return

    # -------------------------------------------------
    # Season
    # -------------------------------------------------

    if data.startswith("season:"):

        season = int(
            data.split(":")[1]
        )

        context.user_data[
            "current_season"
        ] = season

        await show_quality(
            query,
            context,
            season,
        )

        return

    # -------------------------------------------------
    # Quality
    # -------------------------------------------------

    if data.startswith("quality:"):

        quality = data.split(
            ":",
            1,
        )[1]

        if quality not in AVAILABLE_QUALITIES:
            return

        context.user_data[
            "current_quality"
        ] = quality

        await show_languages(
            query,
            context,
            quality,
        )

        return

    # -------------------------------------------------
    # Language
    # -------------------------------------------------

    if data.startswith("lang:"):

        language = data.split(
            ":",
            1,
        )[1]

        if language not in AVAILABLE_LANGUAGES:
            return

        context.user_data[
            "current_language"
        ] = language

        await show_episodes(
            query,
            context,
            page=0,
        )

        return

    # -------------------------------------------------
    # Episodes pagination
    # -------------------------------------------------

    if data.startswith("episodes:"):

        page = int(
            data.split(":")[1]
        )

        await show_episodes(
            query,
            context,
            page,
        )

        return

    # -------------------------------------------------
    # Episode
    # -------------------------------------------------

    if data.startswith("episode:"):

        episode = int(
            data.split(":")[1]
        )

        await open_episode(
            query,
            context,
            episode,
        )

        return

    # -------------------------------------------------
    # Back to anime
    # -------------------------------------------------

    if data == "back_anime":

        anime = context.user_data.get(
            "current_anime"
        )

        if not anime:
            return

        seasons = anime.get(
            "season_count",
            1,
        )

        buttons = [
            [
                InlineKeyboardButton(
                    f"📚 Season {s}",
                    callback_data=f"season:{s}",
                )
            ]
            for s in range(
                1,
                seasons + 1,
            )
        ]

        await query.edit_message_text(
            f"🎬 <b>{anime['name']}</b>\n\n"
            "Select Season:",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                buttons
            ),
        )

        return


# =====================================================
# ERROR HANDLER
# =====================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):

    error = context.error

    logger.error(
        "Unhandled exception: %s",
        error,
    )


# =====================================================
# MAIN
# =====================================================

def main():

    validate_config()

    DatabaseManager.init()

    threading.Thread(
        target=run_health_server,
        daemon=True,
    ).start()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ---------------------------------------------
    # ADD ANIME CONVERSATION
    # ---------------------------------------------

    add_anime_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_add_start,
                pattern=r"^admin:add$",
            )
        ],

        states={

            A_NAME: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_name,
                )
            ],

            A_POSTER: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_poster,
                )
            ],

            A_RATING: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_rating,
                )
            ],

            A_SEASONS: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_seasons,
                )
            ],

            A_EPISODES: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_episodes,
                )
            ],

            A_KEYWORDS: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_add_keywords,
                )
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_admin,
            )
        ],

        per_user=True,
        per_chat=True,
    )

    # ---------------------------------------------
    # ADD EPISODE CONVERSATION
    # ---------------------------------------------

    add_episode_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                admin_episode_start,
                pattern=r"^admin:episode$",
            )
        ],

        states={

            E_ANIME: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_episode_anime,
                )
            ],

            E_SEASON: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_episode_season,
                )
            ],

            E_QUALITY: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_episode_quality,
                )
            ],

            E_LANGUAGE: [
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_episode_language,
                )
            ],

            E_MAPPING: [
                CommandHandler(
                    "done",
                    admin_episode_done,
                ),
                MessageHandler(
                    filters.TEXT
                    & ~filters.COMMAND,
                    admin_episode_mapping,
                ),
            ],
        },

        fallbacks=[
            CommandHandler(
                "cancel",
                cancel_admin,
            )
        ],

        per_user=True,
        per_chat=True,
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "admin",
            admin_panel,
        )
    )

    app.add_handler(
        add_anime_conv
    )

    app.add_handler(
        add_episode_conv
    )

    app.add_handler(
        CallbackQueryHandler(
            callbacks
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_text,
        )
    )

    app.add_error_handler(
        error_handler
    )

    logger.info(
        "Anime Bot is starting..."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
