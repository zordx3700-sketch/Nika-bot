# FILE: admin.py
# CHANGE: Category-first title addition, Series/Seasons/Episodes management, Multi-URL manager without overwriting, and User Requests view

"""
Production-Ready Admin Control Panel for Telegram Anime & Media Bot.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0

Features:
- Restricted strictly to ADMIN_ID with instant authorization check.
- 1. Category-First Title System:
     Admin -> Manage Titles -> Select Category -> Titles in Category -> Add/Edit Title.
- 2. Series & Season & Episode System:
     Title (Type: Series) -> Manage Seasons -> Add Season -> Add Episodes.
- 3. Multi-URL Manager:
     Title (Normal or Episode) -> Language -> Resolution -> Add unlimited Watch/Download URLs independently.
- 4. Keyword System:
     Add/Remove keywords directly linked to Firestore index.
- 5. User Media Requests:
     View latest user requests logged in Firestore.
- 6. Categories, Languages, Resolutions, Broadcast & Statistics management.
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_ID
from database import DatabaseManager
from keyboards import (
    admin_categories_keyboard,
    admin_categories_picker_keyboard,
    admin_category_detail_keyboard,
    admin_dashboard_keyboard,
    admin_episode_detail_keyboard,
    admin_keywords_keyboard,
    admin_languages_keyboard,
    admin_resolutions_keyboard,
    admin_season_detail_keyboard,
    admin_seasons_keyboard,
    admin_stats_keyboard,
    admin_title_detail_keyboard,
    admin_titles_in_category_keyboard,
    admin_url_combo_manage_keyboard,
    admin_url_combos_list_keyboard,
    admin_users_keyboard,
    back_button,
    cancel_action_keyboard,
)

logger = logging.getLogger("AdminHandlers")

# Database Manager
db = DatabaseManager()

# Conversation states
(
    STATE_CAT_ADD,
    STATE_CAT_EDIT,
    STATE_CAT_ORDER,
    STATE_TITLE_ADD_NAME,
    STATE_TITLE_ADD_TYPE,
    STATE_SEASON_ADD_NUM,
    STATE_SEASON_ADD_NAME,
    STATE_EPISODE_ADD_NUM,
    STATE_EPISODE_ADD_NAME,
    STATE_KW_ADD,
    STATE_LANG_ADD,
    STATE_RES_ADD,
    STATE_URL_ADD_WATCH,
    STATE_URL_ADD_DOWNLOAD,
    STATE_HELP_EDIT,
    STATE_BROADCAST_MSG,
) = range(16)


# =========================================================================
# HELPERS & VALIDATION
# =========================================================================

def is_admin(user_id: Optional[int]) -> bool:
    """Verify administrator identity."""
    return user_id is not None and user_id == ADMIN_ID


def is_valid_url(url_str: str) -> bool:
    """Verify HTTP / HTTPS URL syntax."""
    if not url_str:
        return False
    try:
        r = urlparse(url_str.strip())
        return all([r.scheme in ("http", "https"), r.netloc])
    except Exception:
        return False


def cancel_markup() -> InlineKeyboardMarkup:
    """Standard inline cancel markup for active conversation states."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Cancel Action", callback_data="adm_cancel")]
    ])


# =========================================================================
# DASHBOARD ENTRY & CANCEL
# =========================================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /admin dashboard."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text("⛔ *Access Denied.* Admin authorization required.")
        return ConversationHandler.END

    text = (
        "🎛️ *Administrator Control Panel*\n\n"
        "Manage categories, titles, series/episodes, media links, and user analytics:"
    )
    markup = admin_dashboard_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)

    return ConversationHandler.END


async def cancel_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Abort conversation and return to admin dashboard."""
    context.user_data.clear()
    msg = "🚫 *Action cancelled.* Returned to Admin Dashboard."
    if update.callback_query:
        await update.callback_query.answer("Action cancelled.")
        await update.callback_query.edit_message_text(
            msg, reply_markup=admin_dashboard_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    elif update.message:
        await update.message.reply_text(
            msg, reply_markup=admin_dashboard_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    return ConversationHandler.END


# =========================================================================
# 1. CATEGORIES MANAGEMENT
# =========================================================================

async def admin_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List categories in Admin."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    data = query.data or "adm_cats:1"
    page = int(data.split(":")[1]) if ":" in data else 1

    cats = db.get_all_categories(only_enabled=False)
    markup = admin_categories_keyboard(cats, page=page, page_size=6)
    await query.edit_message_text(
        "📂 *Category Management*\n\nSelect a category to edit or create a new one:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View individual category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cat_id = query.data.split(":")[1]
    cat = db.get_category(cat_id)
    if not cat:
        await query.edit_message_text("⚠️ Category not found.", reply_markup=admin_dashboard_keyboard())
        return

    status = "🟢 Enabled" if cat.get("is_enabled", True) else "🔴 Disabled"
    text = (
        f"📂 *Category:* `{cat.get('name')}`\n"
        f"• Status: {status}\n"
        f"• Display Order: `{cat.get('order', 0)}`\n"
        f"• ID: `{cat.get('id')}`"
    )
    markup = admin_category_detail_keyboard(cat_id, bool(cat.get("is_enabled", True)))
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_cat_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle enable/disable status."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    cat_id = parts[1]
    new_state = parts[2] == "1"
    db.set_category_enabled(cat_id, new_state)
    await query.answer(f"Category status set to {'Enabled' if new_state else 'Disabled'}.")
    await admin_cat_view(update, context)


async def admin_cat_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    cat_id = query.data.split(":")[1]
    db.delete_category(cat_id)
    await query.answer("Category deleted.")
    query.data = "adm_cats:1"
    await admin_categories_list(update, context)


async def start_cat_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ *Add New Category*\n\nEnter the name of the new category:",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_ADD


async def handle_cat_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if not name:
        return STATE_CAT_ADD

    cat_id = db.add_category(name=name)
    await update.message.reply_text(
        f"✅ Category *{name}* added successfully (ID: `{cat_id}`).",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def start_cat_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat_id = query.data.split(":")[1]
    context.user_data["edit_cat_id"] = cat_id
    await query.edit_message_text(
        "✏️ *Edit Category Name*\n\nEnter the new name:",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_EDIT


async def handle_cat_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    cat_id = context.user_data.get("edit_cat_id")
    if not name or not cat_id:
        return ConversationHandler.END

    db.edit_category(cat_id, name=name)
    await update.message.reply_text(
        f"✅ Category updated to *{name}*.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def start_cat_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat_id = query.data.split(":")[1]
    context.user_data["order_cat_id"] = cat_id
    await query.edit_message_text(
        "🔢 *Reorder Category*\n\nEnter integer display order (e.g. 1, 2, 5):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_ORDER


async def handle_cat_order_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    cat_id = context.user_data.get("order_cat_id")
    try:
        val = int(text)
        db.edit_category(cat_id, order=val)
        await update.message.reply_text(
            f"✅ Display order updated to `{val}`.",
            reply_markup=admin_dashboard_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await update.message.reply_text("⚠️ Invalid number. Order not updated.")
    return ConversationHandler.END


# =========================================================================
# 2. CATEGORY-FIRST TITLE SYSTEM
# =========================================================================

async def admin_titles_category_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: Admin selects Category to view/add titles inside it."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cats = db.get_all_categories(only_enabled=False)
    markup = admin_categories_picker_keyboard(cats, prefix="adm_t_cat_pick", back_cb="adm_dash")
    await query.edit_message_text(
        "🎬 *Manage Titles (Step 1: Select Category)*\n\nChoose a category to view or add titles:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_titles_in_category_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 2: View titles belonging to the selected category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    # Format: adm_t_cat_pick:<category_id> or adm_t_cat_pick:<category_id>:<page>
    parts = query.data.split(":")
    cat_id = parts[1]
    page = int(parts[2]) if len(parts) >= 3 else 1

    cat_doc = db.get_category(cat_id)
    cat_name = cat_doc.get("name", "Category") if cat_doc else "Category"

    titles = db.get_titles_by_category(cat_id, only_published=False, limit=100)
    markup = admin_titles_in_category_keyboard(
        category_id=cat_id,
        category_name=cat_name,
        titles=titles,
        page=page,
        page_size=6,
    )
    await query.edit_message_text(
        f"🎬 *Titles in:* `{cat_name}`\n\nSelect a title to manage or tap **➕ Add Title**:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_title_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3: Ask for title name inside selected category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    cat_id = query.data.split(":")[1]
    context.user_data["new_title_cat_id"] = cat_id

    cat_doc = db.get_category(cat_id)
    cat_name = cat_doc.get("name", "Category") if cat_doc else "Category"

    await query.edit_message_text(
        f"➕ *Add Title to:* `{cat_name}`\n\nEnter the title name (e.g. *Solo Leveling*, *Oppenheimer*):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_NAME


async def handle_title_add_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive title name, then ask for Content Type (Normal vs Series)."""
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("⚠️ Title name cannot be empty:")
        return STATE_TITLE_ADD_NAME

    context.user_data["new_title_name"] = name
    cat_id = context.user_data.get("new_title_cat_id", "")

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="🎬 Normal (Movie / Standalone)", callback_data="set_type_normal"),
            InlineKeyboardButton(text="📺 Series (Seasons & Episodes)", callback_data="set_type_series"),
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel")],
    ])

    await update.message.reply_text(
        f"🎬 Title Name: *{name}*\n\nSelect the content structure:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_TYPE


async def handle_title_add_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save title in selected category with specified content type."""
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()

    c_type = "series" if query.data == "set_type_series" else "normal"
    name = context.user_data.get("new_title_name", "Untitled")
    cat_id = context.user_data.get("new_title_cat_id", "")

    title_id = db.add_title(
        title=name,
        category_ids=[cat_id] if cat_id else [],
        content_type=c_type,
        is_published=True,
    )

    type_lbl = "Series (Seasons & Episodes)" if c_type == "series" else "Movie / Standalone"
    await query.edit_message_text(
        f"✅ *Title Created Successfully!*\n\n"
        f"• Title: *{name}*\n"
        f"• Type: `{type_lbl}`\n"
        f"• ID: `{title_id}`\n\n"
        "You can now manage seasons/episodes or configure URLs.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_title_detail_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View details and options of a single title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) >= 3 else ""

    title_doc = db.get_title(title_id)
    if not title_doc:
        await query.edit_message_text("⚠️ Title not found.", reply_markup=admin_dashboard_keyboard())
        return

    c_type = title_doc.get("content_type", "normal")
    is_series = c_type == "series"
    status = "🟢 Published" if title_doc.get("is_published", True) else "🔴 Draft"
    kws = ", ".join(title_doc.get("keywords", [])) or "None"

    text = (
        f"{'📺' if is_series else '🎬'} *Title:* `{title_doc.get('title')}`\n"
        f"• Type: `{'Series' if is_series else 'Movie/Normal'}`\n"
        f"• Status: {status}\n"
        f"• Keywords: _{kws}_\n"
        f"• ID: `{title_id}`"
    )
    markup = admin_title_detail_keyboard(
        title_id=title_id,
        category_id=cat_id,
        is_published=bool(title_doc.get("is_published", True)),
        is_series=is_series,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_title_toggle_pub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle title published/draft."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2]
    new_state = parts[3] == "1"

    db.edit_title(title_id, is_published=new_state)
    await query.answer(f"Title set to {'Published' if new_state else 'Draft'}.")
    query.data = f"adm_t_v:{title_id}:{cat_id}"
    await admin_title_detail_view(update, context)


async def admin_title_switch_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch content type between normal and series."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2]

    title_doc = db.get_title(title_id)
    curr_type = title_doc.get("content_type", "normal") if title_doc else "normal"
    new_type = "series" if curr_type == "normal" else "normal"

    db.edit_title(title_id, content_type=new_type)
    await query.answer(f"Switched type to {new_type.upper()}.")
    query.data = f"adm_t_v:{title_id}:{cat_id}"
    await admin_title_detail_view(update, context)


async def admin_title_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2]

    db.delete_title(title_id)
    await query.answer("Title deleted.")
    query.data = f"adm_t_cat_pick:{cat_id}"
    await admin_titles_in_category_view(update, context)


# =========================================================================
# 3. SERIES MANAGEMENT (SEASONS & EPISODES)
# =========================================================================

async def admin_seasons_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List seasons of a series."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2]

    title_doc = db.get_title(title_id)
    t_name = title_doc.get("title", "Series") if title_doc else "Series"

    seasons = db.get_seasons(title_id)
    markup = admin_seasons_keyboard(title_id=title_id, category_id=cat_id, seasons=seasons)
    await query.edit_message_text(
        f"📺 *Manage Seasons for:* `{t_name}`\n\nSelect a season or tap **➕ New Season**:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_season_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for Season Number."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    context.user_data["s_add_title_id"] = parts[1]
    context.user_data["s_add_cat_id"] = parts[2]

    await query.edit_message_text(
        "📚 *Add Season (Step 1/2)*\n\nEnter the season number (e.g. `1`, `2`, `3`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_SEASON_ADD_NUM


async def handle_season_add_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    try:
        num = int(text)
        context.user_data["s_add_num"] = num
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. 1, 2):")
        return STATE_SEASON_ADD_NUM

    await update.message.reply_text(
        f"📚 Season Number: `{num}`\n\n*(Step 2/2)* Enter season display name (e.g. `Season 1`, or send `-` for default):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_SEASON_ADD_NAME


async def handle_season_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    s_name = "" if text == "-" else text

    title_id = context.user_data.get("s_add_title_id")
    cat_id = context.user_data.get("s_add_cat_id")
    num = context.user_data.get("s_add_num", 1)

    if not title_id:
        return ConversationHandler.END

    season_id = db.add_season(title_id=title_id, season_number=num, season_name=s_name)
    await update.message.reply_text(
        f"✅ Season `{s_name or f'Season {num}'}` added successfully (ID: `{season_id}`).",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_season_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View episodes in a season."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    cat_id = parts[3]

    season_doc = db.get_season(title_id, season_id)
    s_name = season_doc.get("season_name", "Season") if season_doc else "Season"

    episodes = db.get_episodes(title_id, season_id)
    markup = admin_season_detail_keyboard(
        title_id=title_id,
        season_id=season_id,
        category_id=cat_id,
        episodes=episodes,
    )
    await query.edit_message_text(
        f"📚 *Manage Episodes for:* `{s_name}`\n\nConfigured episodes ({len(episodes)}):\nSelect an episode to manage URLs:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_season_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a season."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    cat_id = parts[3]

    db.delete_season(title_id, season_id)
    await query.answer("Season deleted.")
    query.data = f"adm_s_list:{title_id}:{cat_id}"
    await admin_seasons_list(update, context)


async def start_episode_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for episode number."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    context.user_data["ep_add_title_id"] = parts[1]
    context.user_data["ep_add_season_id"] = parts[2]
    context.user_data["ep_add_cat_id"] = parts[3]

    await query.edit_message_text(
        "🎬 *Add Episode (Step 1/2)*\n\nEnter episode number (e.g. `1`, `2`, `24`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_EPISODE_ADD_NUM


async def handle_episode_add_num(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    try:
        num = int(text)
        context.user_data["ep_add_num"] = num
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. 1, 5):")
        return STATE_EPISODE_ADD_NUM

    await update.message.reply_text(
        f"🎬 Episode Number: `{num}`\n\n*(Step 2/2)* Enter episode title (e.g. `Episode 1`, or send `-` for default):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_EPISODE_ADD_NAME


async def handle_episode_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    ep_name = "" if text == "-" else text

    title_id = context.user_data.get("ep_add_title_id")
    season_id = context.user_data.get("ep_add_season_id")
    num = context.user_data.get("ep_add_num", 1)

    if not title_id or not season_id:
        return ConversationHandler.END

    ep_id = db.add_episode(
        title_id=title_id,
        season_id=season_id,
        episode_number=num,
        episode_title=ep_name,
    )
    await update.message.reply_text(
        f"✅ Episode `{ep_name or f'Episode {num}'}` added successfully (ID: `{ep_id}`).",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_episode_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View individual episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    episode_id = parts[3]
    cat_id = parts[4]

    ep_doc = db.get_episode(title_id, season_id, episode_id)
    ep_name = ep_doc.get("episode_title", "Episode") if ep_doc else "Episode"

    markup = admin_episode_detail_keyboard(
        title_id=title_id,
        season_id=season_id,
        episode_id=episode_id,
        category_id=cat_id,
    )
    await query.edit_message_text(
        f"🎬 *Episode:* `{ep_name}`\n\nManage links or options:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_episode_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    episode_id = parts[3]
    cat_id = parts[4]

    db.delete_episode(title_id, season_id, episode_id)
    await query.answer("Episode deleted.")
    query.data = f"adm_s_v:{title_id}:{season_id}:{cat_id}"
    await admin_season_view(update, context)


# =========================================================================
# 4. MULTI-URL MANAGER
# =========================================================================

async def admin_url_combos_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View combinations for Normal Title or Episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    if parts[0] == "adm_u_m":
        # Normal Title: adm_u_m:<title_id>:<category_id>
        title_id = parts[1]
        cat_id = parts[2] if len(parts) >= 3 else ""
        combos = db.get_all_media_combos_for_title(title_id)
        markup = admin_url_combos_list_keyboard(title_id, combos, category_id=cat_id)
    else:
        # Episode: adm_u_ep_m:<title_id>:<season_id>:<episode_id>:<category_id>
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        cat_id = parts[4] if len(parts) >= 5 else ""
        combos = db.get_all_media_combos_for_title(title_id, season_id=season_id, episode_id=episode_id)
        markup = admin_url_combos_list_keyboard(
            title_id, combos, category_id=cat_id, season_id=season_id, episode_id=episode_id
        )

    await query.edit_message_text(
        "🔗 *URL Combination Manager*\n\nSelect a combination to manage URLs or tap **➕ Add URL Combination**:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_url_combo_detail_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View & manage specific Language + Resolution combination."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    if len(parts) == 5:
        # Normal: adm_u_combo_v:<title_id>:<lang>:<res>:<category_id>
        title_id = parts[1]
        lang = parts[2]
        res = parts[3]
        cat_id = parts[4]
        season_id, episode_id = None, None
        combo_data = db.get_media_url_combo(title_id, language=lang, resolution=res) or {}
    else:
        # Episode: adm_u_combo_v:<title_id>:<season_id>:<episode_id>:<lang>:<res>:<category_id>
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]
        res = parts[5]
        cat_id = parts[6]
        combo_data = (
            db.get_media_url_combo(title_id, language=lang, resolution=res, season_id=season_id, episode_id=episode_id)
            or {}
        )

    w_urls = combo_data.get("watch_urls", [])
    dl_urls = combo_data.get("download_urls", [])

    text = (
        f"🔗 *Combination Details*\n"
        f"• Language: `{lang}`\n"
        f"• Quality: `{res}`\n\n"
        f"▶️ *Watch URLs ({len(w_urls)}):*\n"
        + ("\n".join(f"  {i+1}. {u}" for i, u in enumerate(w_urls)) if w_urls else "  None")
        + f"\n\n📥 *Download URLs ({len(dl_urls)}):*\n"
        + ("\n".join(f"  {i+1}. {u}" for i, u in enumerate(dl_urls)) if dl_urls else "  None")
    )
    markup = admin_url_combo_manage_keyboard(
        title_id=title_id,
        language=lang,
        resolution=res,
        combo_data=combo_data,
        category_id=cat_id,
        season_id=season_id,
        episode_id=episode_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_add_url_combo_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: Pick Language for new combo."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    is_ep = parts[0] == "adm_u_add_ep"
    title_id = parts[1]

    langs = db.get_available_languages(only_enabled=True)
    keyboard = []
    for l in langs:
        l_name = l.get("name", "Lang")
        if is_ep:
            season_id = parts[2]
            episode_id = parts[3]
            cat_id = parts[4]
            cb = f"adm_u_setlang_ep:{title_id}:{season_id}:{episode_id}:{l_name}:{cat_id}"
        else:
            cat_id = parts[2] if len(parts) >= 3 else ""
            cb = f"adm_u_setlang:{title_id}:{l_name}:{cat_id}"

        keyboard.append([InlineKeyboardButton(text=f"🗣️ {l_name}", callback_data=cb)])

    back_cb = f"adm_u_ep_m:{title_id}:{parts[2]}:{parts[3]}:{parts[4]}" if is_ep else f"adm_u_m:{title_id}:{cat_id}"
    keyboard.append([back_button(back_cb)])

    await query.edit_message_text(
        "🔗 *Add URL Combination (Step 1/2: Language)*\n\nChoose language for this combination:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_add_url_combo_res(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 2: Pick Resolution for new combo."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    is_ep = parts[0] == "adm_u_setlang_ep"
    title_id = parts[1]

    if is_ep:
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]
        cat_id = parts[5]
    else:
        lang = parts[2]
        cat_id = parts[3]

    resols = db.get_available_resolutions(only_enabled=True)
    keyboard = []
    for r in resols:
        r_name = r.get("name", "Res")
        if is_ep:
            cb = f"adm_u_combo_v:{title_id}:{season_id}:{episode_id}:{lang}:{r_name}:{cat_id}"
        else:
            cb = f"adm_u_combo_v:{title_id}:{lang}:{r_name}:{cat_id}"

        keyboard.append([InlineKeyboardButton(text=f"🎞️ {r_name}", callback_data=cb)])

    keyboard.append([back_button("adm_dash")])
    await query.edit_message_text(
        f"🔗 *Add URL Combination (Step 2/2: Resolution)*\nLanguage: `{lang}`\n\nChoose resolution:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_url_add_watch_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for new Watch URL input."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    if len(parts) == 5:
        # Normal: adm_u_aw:<title_id>:<lang>:<res>:<category_id>
        context.user_data["add_url_title_id"] = parts[1]
        context.user_data["add_url_lang"] = parts[2]
        context.user_data["add_url_res"] = parts[3]
        context.user_data["add_url_cat_id"] = parts[4]
        context.user_data["add_url_season_id"] = None
        context.user_data["add_url_episode_id"] = None
    else:
        # Episode: adm_u_aw:<title_id>:<season_id>:<episode_id>:<lang>:<res>:<category_id>
        context.user_data["add_url_title_id"] = parts[1]
        context.user_data["add_url_season_id"] = parts[2]
        context.user_data["add_url_episode_id"] = parts[3]
        context.user_data["add_url_lang"] = parts[4]
        context.user_data["add_url_res"] = parts[5]
        context.user_data["add_url_cat_id"] = parts[6]

    context.user_data["add_url_type"] = "watch"

    await query.edit_message_text(
        "▶️ *Add Watch URL*\n\nEnter the streaming HTTPS URL (e.g. `https://stream.example.com/watch`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_URL_ADD_WATCH


async def handle_url_add_watch_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not is_valid_url(text):
        await update.message.reply_text("⚠️ Invalid URL. Must start with http:// or https://:")
        return STATE_URL_ADD_WATCH

    title_id = context.user_data.get("add_url_title_id")
    lang = context.user_data.get("add_url_lang")
    res = context.user_data.get("add_url_res")
    s_id = context.user_data.get("add_url_season_id")
    ep_id = context.user_data.get("add_url_episode_id")

    db.add_media_url_link(
        title_id=title_id,
        language=lang,
        resolution=res,
        url=text,
        url_type="watch",
        season_id=s_id,
        episode_id=ep_id,
    )

    await update.message.reply_text(
        f"✅ *Watch URL Added!*\n`{text}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def start_url_add_dl_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for new Download URL input."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    if len(parts) == 5:
        context.user_data["add_url_title_id"] = parts[1]
        context.user_data["add_url_lang"] = parts[2]
        context.user_data["add_url_res"] = parts[3]
        context.user_data["add_url_cat_id"] = parts[4]
        context.user_data["add_url_season_id"] = None
        context.user_data["add_url_episode_id"] = None
    else:
        context.user_data["add_url_title_id"] = parts[1]
        context.user_data["add_url_season_id"] = parts[2]
        context.user_data["add_url_episode_id"] = parts[3]
        context.user_data["add_url_lang"] = parts[4]
        context.user_data["add_url_res"] = parts[5]
        context.user_data["add_url_cat_id"] = parts[6]

    context.user_data["add_url_type"] = "download"

    await query.edit_message_text(
        "📥 *Add Download URL*\n\nEnter direct download HTTPS link (e.g. `https://files.example.com/download`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_URL_ADD_DOWNLOAD


async def handle_url_add_dl_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if not is_valid_url(text):
        await update.message.reply_text("⚠️ Invalid URL. Must start with http:// or https://:")
        return STATE_URL_ADD_DOWNLOAD

    title_id = context.user_data.get("add_url_title_id")
    lang = context.user_data.get("add_url_lang")
    res = context.user_data.get("add_url_res")
    s_id = context.user_data.get("add_url_season_id")
    ep_id = context.user_data.get("add_url_episode_id")

    db.add_media_url_link(
        title_id=title_id,
        language=lang,
        resolution=res,
        url=text,
        url_type="download",
        season_id=s_id,
        episode_id=ep_id,
    )

    await update.message.reply_text(
        f"✅ *Download URL Added!*\n`{text}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_url_delete_single(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a single URL from watch/download list."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    is_watch = parts[0] == "adm_u_dw"

    if len(parts) == 6:
        # Normal: adm_u_dw:<title_id>:<lang>:<res>:<idx>:<cat_id>
        title_id = parts[1]
        lang = parts[2]
        res = parts[3]
        idx = int(parts[4])
        cat_id = parts[5]
        combo = db.get_media_url_combo(title_id, language=lang, resolution=res) or {}
        urls = combo.get("watch_urls" if is_watch else "download_urls", [])
        if 0 <= idx < len(urls):
            target_url = urls[idx]
            db.remove_media_url_link(
                title_id=title_id,
                language=lang,
                resolution=res,
                url=target_url,
                url_type="watch" if is_watch else "download",
            )
            await query.answer("URL deleted.")
        query.data = f"adm_u_combo_v:{title_id}:{lang}:{res}:{cat_id}"
    else:
        # Episode: adm_u_dw:<title_id>:<season_id>:<episode_id>:<lang>:<res>:<idx>:<cat_id>
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]
        res = parts[5]
        idx = int(parts[6])
        cat_id = parts[7]
        combo = (
            db.get_media_url_combo(title_id, language=lang, resolution=res, season_id=season_id, episode_id=episode_id)
            or {}
        )
        urls = combo.get("watch_urls" if is_watch else "download_urls", [])
        if 0 <= idx < len(urls):
            target_url = urls[idx]
            db.remove_media_url_link(
                title_id=title_id,
                language=lang,
                resolution=res,
                url=target_url,
                url_type="watch" if is_watch else "download",
                season_id=season_id,
                episode_id=episode_id,
            )
            await query.answer("URL deleted.")
        query.data = f"adm_u_combo_v:{title_id}:{season_id}:{episode_id}:{lang}:{res}:{cat_id}"

    await admin_url_combo_detail_view(update, context)


async def admin_url_delete_combo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete entire combination."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    if len(parts) == 5:
        title_id = parts[1]
        lang = parts[2]
        res = parts[3]
        cat_id = parts[4]
        db.delete_media_combo(title_id, language=lang, resolution=res)
        await query.answer("Combination deleted.")
        query.data = f"adm_u_m:{title_id}:{cat_id}"
    else:
        title_id = parts[1]
        season_id = parts[2]
        episode_id = parts[3]
        lang = parts[4]
        res = parts[5]
        cat_id = parts[6]
        db.delete_media_combo(title_id, language=lang, resolution=res, season_id=season_id, episode_id=episode_id)
        await query.answer("Combination deleted.")
        query.data = f"adm_u_ep_m:{title_id}:{season_id}:{episode_id}:{cat_id}"

    await admin_url_combos_view(update, context)


# =========================================================================
# 5. KEYWORDS MANAGEMENT
# =========================================================================

async def admin_keywords_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Keywords list for a title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) >= 3 else ""

    title_doc = db.get_title(title_id)
    kws = title_doc.get("keywords", []) if title_doc else []

    markup = admin_keywords_keyboard(title_id=title_id, category_id=cat_id, keywords=kws)
    await query.edit_message_text(
        f"🏷️ *Keywords for:* `{title_doc.get('title') if title_doc else 'Title'}`\n\n"
        f"Current: {', '.join(kws) if kws else 'None'}",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_kw_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    context.user_data["kw_title_id"] = parts[1]
    context.user_data["kw_cat_id"] = parts[2] if len(parts) >= 3 else ""

    await query.edit_message_text(
        "🏷️ *Add Search Keywords*\n\nEnter keywords (comma-separated or single word):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_KW_ADD


async def handle_kw_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    title_id = context.user_data.get("kw_title_id")
    if not text or not title_id:
        return ConversationHandler.END

    for item in text.split(","):
        kw = item.strip()
        if kw:
            db.add_keyword(title_id, kw)

    await update.message.reply_text(
        "✅ Keywords added successfully.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_kw_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    kw = parts[2]
    cat_id = parts[3] if len(parts) >= 4 else ""

    db.remove_keyword(title_id, kw)
    await query.answer(f"Removed '{kw}'.")
    query.data = f"adm_kw_m:{title_id}:{cat_id}"
    await admin_keywords_view(update, context)


# =========================================================================
# 6. USER REQUESTS & STATS & BROADCAST
# =========================================================================

async def admin_requests_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View latest user requests logged in Firestore."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    reqs = db.get_recent_requests(limit=15)
    if not reqs:
        text = "📩 *User Media Requests*\n\nNo pending requests recorded."
    else:
        lines = []
        for r in reqs:
            u_name = r.get("username") or r.get("first_name", "User")
            r_text = r.get("request_text", "")
            lines.append(f"• *{u_name}:* `{r_text}`")
        text = "📩 *Recent User Media Requests:*\n\n" + "\n".join(lines)

    markup = InlineKeyboardMarkup([[back_button("adm_dash")]])
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_stats_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View bot usage statistics."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total_users = db.get_total_users()
    top_kws = db.get_top_searched_keywords(limit=8)
    kw_lines = [f"{i+1}. `{k['keyword']}` ({k['count']} searches)" for i, k in enumerate(top_kws)]
    kw_str = "\n".join(kw_lines) or "No search history recorded yet."

    text = (
        "📊 *Bot Analytics & Statistics*\n\n"
        f"👥 *Total Registered Members:* `{total_users}`\n\n"
        f"🔥 *Top Searched Queries:*\n{kw_str}"
    )
    markup = admin_stats_keyboard()
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_users_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Users overview & broadcast trigger."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total = db.get_total_users()
    markup = admin_users_keyboard(total)
    await query.edit_message_text(
        f"👥 *Users Overview*\n\nTotal registered members: `{total}`",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    await query.edit_message_text(
        "📢 *Broadcast Message to All Users*\n\nSend the message text you wish to broadcast:",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_BROADCAST_MSG


async def handle_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if not text:
        return STATE_BROADCAST_MSG

    status = await update.message.reply_text("⏳ *Broadcasting message...*", parse_mode=ParseMode.MARKDOWN)
    success, fail = 0, 0

    for user_doc in db.users_col.stream():
        uid = (user_doc.to_dict() or {}).get("user_id")
        if uid:
            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.MARKDOWN)
                success += 1
            except Exception:
                fail += 1

    await status.edit_text(
        f"📢 *Broadcast Complete!*\n\n✅ Delivered: `{success}`\n❌ Failed: `{fail}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# 7. LANGUAGES & RESOLUTIONS
# =========================================================================

async def admin_languages_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    langs = db.get_available_languages(only_enabled=False)
    markup = admin_languages_keyboard(langs)
    await query.edit_message_text(
        "🌐 *Language Management*\n\nConfigure available languages:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_lang_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    lang_id = query.data.split(":")[1]
    doc = db.languages_col.document(lang_id).get()
    if doc.exists:
        curr = doc.to_dict().get("is_enabled", True)
        db.set_language_enabled(lang_id, not curr)
        await query.answer(f"Language {'Disabled' if curr else 'Enabled'}.")
    await admin_languages_list(update, context)


async def start_lang_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    await query.edit_message_text(
        "➕ *Add New Language*\n\nEnter language name (e.g. `Hindi`, `English`, `Japanese`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_LANG_ADD


async def handle_lang_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if not name:
        return STATE_LANG_ADD
    db.add_language(name=name)
    await update.message.reply_text(
        f"✅ Language *{name}* added successfully.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_resolutions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    resols = db.get_available_resolutions(only_enabled=False)
    markup = admin_resolutions_keyboard(resols)
    await query.edit_message_text(
        "🎞️ *Resolution Management*\n\nConfigure quality options (480p, 720p, 1080p, 4K):",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_res_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    res_id = query.data.split(":")[1]
    doc = db.resolutions_col.document(res_id).get()
    if doc.exists:
        curr = doc.to_dict().get("is_enabled", True)
        db.set_resolution_enabled(res_id, not curr)
        await query.answer(f"Resolution {'Disabled' if curr else 'Enabled'}.")
    await admin_resolutions_list(update, context)


async def start_res_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    await query.edit_message_text(
        "➕ *Add Resolution Quality*\n\nEnter resolution name (e.g. `480p`, `720p HD`, `1080p FHD`, `4K UHD`):",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_RES_ADD


async def handle_res_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if not name:
        return STATE_RES_ADD
    db.add_resolution(name=name)
    await update.message.reply_text(
        f"✅ Resolution *{name}* added successfully.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# 8. HELP TEXT EDITOR
# =========================================================================

async def start_help_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    curr_help = db.get_help_text()
    await query.edit_message_text(
        f"📝 *Edit Bot Help Guide*\n\nCurrent help text:\n_{curr_help}_\n\n"
        "Send the new formatted Markdown text:",
        reply_markup=cancel_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_HELP_EDIT


async def handle_help_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text:
        db.set_help_text(text)
        await update.message.reply_text(
            "✅ Help guide updated successfully.",
            reply_markup=admin_dashboard_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    return ConversationHandler.END


# =========================================================================
# HANDLER REGISTRATION
# =========================================================================

def register_admin_handlers(app: Application) -> None:
    """Register all Admin command, callback, and ConversationHandler flows."""

    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_command),
            CallbackQueryHandler(admin_command, pattern="^adm_dash$"),
            CallbackQueryHandler(start_cat_add, pattern="^adm_cat_add$"),
            CallbackQueryHandler(start_cat_edit, pattern="^adm_cat_e:"),
            CallbackQueryHandler(start_cat_order, pattern="^adm_cat_o:"),
            CallbackQueryHandler(start_title_add, pattern="^adm_t_add:"),
            CallbackQueryHandler(start_season_add, pattern="^adm_s_add:"),
            CallbackQueryHandler(start_episode_add, pattern="^adm_ep_add:"),
            CallbackQueryHandler(start_kw_add, pattern="^adm_kw_add:"),
            CallbackQueryHandler(start_url_add_watch_prompt, pattern="^adm_u_aw:"),
            CallbackQueryHandler(start_url_add_dl_prompt, pattern="^adm_u_adl:"),
            CallbackQueryHandler(start_lang_add, pattern="^adm_lang_add$"),
            CallbackQueryHandler(start_res_add, pattern="^adm_res_add$"),
            CallbackQueryHandler(start_broadcast, pattern="^adm_broadcast$"),
            CallbackQueryHandler(start_help_edit, pattern="^adm_help_edit$"),
        ],
        states={
            STATE_CAT_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_add_input)],
            STATE_CAT_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_edit_input)],
            STATE_CAT_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_order_input)],
            STATE_TITLE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_add_name_input)],
            STATE_TITLE_ADD_TYPE: [CallbackQueryHandler(handle_title_add_type_callback, pattern="^set_type_")],
            STATE_SEASON_ADD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_season_add_num)],
            STATE_SEASON_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_season_add_name)],
            STATE_EPISODE_ADD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_episode_add_num)],
            STATE_EPISODE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_episode_add_name)],
            STATE_KW_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kw_add_input)],
            STATE_LANG_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lang_add_input)],
            STATE_RES_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_res_add_input)],
            STATE_URL_ADD_WATCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_add_watch_input)],
            STATE_URL_ADD_DOWNLOAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_add_dl_input)],
            STATE_BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_input)],
            STATE_HELP_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_edit_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_admin_state),
            CallbackQueryHandler(cancel_admin_state, pattern="^adm_cancel$"),
        ],
        per_chat=True,
    )
    app.add_handler(admin_conv)

    # Categories management callbacks
    app.add_handler(CallbackQueryHandler(admin_categories_list, pattern="^adm_cats"))
    app.add_handler(CallbackQueryHandler(admin_cat_view, pattern="^adm_cat_v:"))
    app.add_handler(CallbackQueryHandler(admin_cat_toggle, pattern="^adm_cat_t:"))
    app.add_handler(CallbackQueryHandler(admin_cat_delete, pattern="^adm_cat_d:"))

    # Category-First Titles callbacks
    app.add_handler(CallbackQueryHandler(admin_titles_category_picker, pattern="^adm_titles_cat$"))
    app.add_handler(CallbackQueryHandler(admin_titles_in_category_view, pattern="^adm_t_cat_pick:"))
    app.add_handler(CallbackQueryHandler(admin_title_detail_view, pattern="^adm_t_v:"))
    app.add_handler(CallbackQueryHandler(admin_title_toggle_pub, pattern="^adm_t_pub:"))
    app.add_handler(CallbackQueryHandler(admin_title_switch_type, pattern="^adm_t_sw_type:"))
    app.add_handler(CallbackQueryHandler(admin_title_delete, pattern="^adm_t_del:"))

    # Seasons & Episodes callbacks
    app.add_handler(CallbackQueryHandler(admin_seasons_list, pattern="^adm_s_list:"))
    app.add_handler(CallbackQueryHandler(admin_season_view, pattern="^adm_s_v:"))
    app.add_handler(CallbackQueryHandler(admin_season_delete, pattern="^adm_s_del:"))
    app.add_handler(CallbackQueryHandler(admin_episode_view, pattern="^adm_ep_v:"))
    app.add_handler(CallbackQueryHandler(admin_episode_delete, pattern="^adm_ep_del:"))

    # URL Manager & Combinations callbacks
    app.add_handler(
        CallbackQueryHandler(
            lambda u, c: admin_titles_category_picker(
                type("Obj", (object,), {"callback_query": u.callback_query})(), c
            ),
            pattern="^adm_urls_cat$",
        )
    )
    app.add_handler(CallbackQueryHandler(admin_url_combos_view, pattern="^(adm_u_m|adm_u_ep_m|adm_u_s_m):"))
    app.add_handler(CallbackQueryHandler(admin_url_combo_detail_view, pattern="^adm_u_combo_v:"))
    app.add_handler(CallbackQueryHandler(start_add_url_combo_lang, pattern="^(adm_u_add|adm_u_add_ep):"))
    app.add_handler(CallbackQueryHandler(start_add_url_combo_res, pattern="^(adm_u_setlang|adm_u_setlang_ep):"))
    app.add_handler(CallbackQueryHandler(admin_url_delete_single, pattern="^(adm_u_dw|adm_u_ddl):"))
    app.add_handler(CallbackQueryHandler(admin_url_delete_combo, pattern="^adm_u_cdel:"))

    # Keywords callbacks
    app.add_handler(
        CallbackQueryHandler(
            lambda u, c: admin_titles_category_picker(
                type("Obj", (object,), {"callback_query": u.callback_query})(), c
            ),
            pattern="^adm_kws_cat$",
        )
    )
    app.add_handler(CallbackQueryHandler(admin_keywords_view, pattern="^adm_kw_m:"))
    app.add_handler(CallbackQueryHandler(admin_kw_remove, pattern="^adm_kw_rm:"))

    # Requests, Stats & Users callbacks
    app.add_handler(CallbackQueryHandler(admin_requests_view, pattern="^adm_reqs$"))
    app.add_handler(CallbackQueryHandler(admin_stats_view, pattern="^adm_stats"))
    app.add_handler(CallbackQueryHandler(admin_users_view, pattern="^adm_users$"))

    # Languages & Resolutions callbacks
    app.add_handler(CallbackQueryHandler(admin_languages_list, pattern="^adm_langs$"))
    app.add_handler(CallbackQueryHandler(admin_lang_toggle, pattern="^adm_lang_t:"))
    app.add_handler(CallbackQueryHandler(admin_resolutions_list, pattern="^adm_resols$"))
    app.add_handler(CallbackQueryHandler(admin_res_toggle, pattern="^adm_res_t:"))
