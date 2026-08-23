# FILE: admin.py
# CHANGE: Added persistent Add buttons (Season, Episode, Language, Regulation, Link/Button), unified hierarchical URL manager, and full Category-First title flow

"""
Production Admin Module for Telegram Anime & Media Bot.

Compatible with:
- python-telegram-bot: >=22.0, <23.0

Features:
- Strict ADMIN_ID security authentication
- Category-First Title creation flow
- Persistent Add buttons:
    * Manage Seasons -> ➕ Add Season (always visible)
    * Manage Episodes -> ➕ Add Episode (always visible)
    * Manage Languages -> ➕ Add Language (always visible)
    * Manage Regulations -> ➕ Add Regulation (always visible)
    * Manage Links/Buttons -> ➕ Add Link / Button (always visible)
- Unlimited multi-button URLs with custom labels (Download, Watch, Telegram, Server 2, etc.)
- Multi-step ConversationHandlers with validation and easy cancellation
- Category management (Add, Edit, Reorder, Enable/Disable, Delete)
- Keywords and Aliases manager
- User requests inbox & Help text editor
- Comprehensive system statistics
"""

import logging
from typing import Any, Dict, List, Optional

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
    admin_content_languages_keyboard,
    admin_content_links_keyboard,
    admin_content_regulations_keyboard,
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
    admin_users_keyboard,
    back_button,
    cancel_action_keyboard,
)

logger = logging.getLogger("AdminPanel")
db = DatabaseManager()

# =========================================================================
# CONVERSATION STATE CONSTANTS
# =========================================================================
(
    STATE_CAT_ADD_NAME,
    STATE_CAT_EDIT_NAME,
    STATE_CAT_REORDER,
    STATE_TITLE_ADD_NAME,
    STATE_TITLE_CHOOSE_TYPE,
    STATE_TITLE_ADD_KEYWORD,
    STATE_SEASON_ADD_NUM,
    STATE_SEASON_ADD_NAME,
    STATE_EPISODE_ADD_NUM,
    STATE_EPISODE_ADD_NAME,
    STATE_LANG_ADD_NAME,
    STATE_REG_ADD_NAME,
    STATE_LINK_ADD_URL,
    STATE_LINK_ADD_LABEL,
    STATE_HELP_EDIT_TEXT,
    STATE_BROADCAST_TEXT,
) = range(16)


# =========================================================================
# ADMIN AUTHENTICATION GUARD
# =========================================================================

def is_admin(user_id: Optional[int]) -> bool:
    """Validate user ID against configured ADMIN_ID."""
    if not ADMIN_ID or not user_id:
        return False
    return int(user_id) == int(ADMIN_ID)


async def admin_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /admin command."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        return

    text = (
        f"👑 *Admin Control Panel*\n"
        f"Welcome, {user.first_name} (`{user.id}`).\n\n"
        f"Select a management module below:"
    )
    markup = admin_dashboard_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)
    elif update.message:
        await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to admin main dashboard."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()
    await admin_start_command(update, context)


async def cancel_admin_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Generic cancel handler for all admin conversations."""
    query = update.callback_query
    if query:
        await query.answer("Operation cancelled.")
    await admin_start_command(update, context)
    return ConversationHandler.END


# =========================================================================
# 1. CATEGORY MANAGEMENT
# =========================================================================

async def admin_categories_list_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all categories with pagination."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

    cats = db.get_all_categories()
    text = "📂 *Category Management*\n\nSelect a category to edit or tap **➕ Add New Category**:"
    markup = admin_categories_keyboard(cats, page=page)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_category_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for new category name."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    await query.edit_message_text(
        "➕ *Add New Category*\n\nEnter the category name (e.g. `Anime`, `Movie`, `Web Series`, `South Movie`):",
        reply_markup=cancel_action_keyboard(callback_data="adm_cats"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_ADD_NAME


async def handle_category_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save new category."""
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("⚠️ Name cannot be empty. Try again:")
        return STATE_CAT_ADD_NAME

    db.add_category(name=name)
    await update.message.reply_text(
        f"✅ *Category Created:* `{name}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_category_detail_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show details and controls for a single category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cat_id = query.data.split(":")[1]
    cat = db.get_category(cat_id)
    if not cat:
        await query.answer("Category not found.", show_alert=True)
        return

    name = cat.get("name", "Category")
    is_en = cat.get("is_enabled", True)
    order = cat.get("order", 0)

    text = (
        f"📂 *Category Details*\n\n"
        f"• **Name:** `{name}`\n"
        f"• **Status:** {'🟢 Enabled' if is_en else '🔴 Disabled'}\n"
        f"• **Sort Order:** `{order}`\n"
    )
    markup = admin_category_detail_keyboard(cat_id, is_enabled=is_en)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_category_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle enable/disable status for category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    cat_id = parts[1]
    new_val = parts[2] == "1"

    db.set_category_enabled(cat_id, is_enabled=new_val)
    await query.answer("Status updated.")
    query.data = f"adm_cat_v:{cat_id}"
    await admin_category_detail_view(update, context)


async def admin_category_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    cat_id = query.data.split(":")[1]
    db.delete_category(cat_id)
    await query.answer("Category deleted.")
    query.data = "adm_cats:1"
    await admin_categories_list_view(update, context)


# =========================================================================
# 2. CATEGORY-FIRST TITLE MANAGEMENT
# =========================================================================

async def admin_titles_choose_category_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: Pick category to manage or add titles."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cats = db.get_all_categories()
    if not cats:
        await query.edit_message_text(
            "⚠️ *No Categories Found!*\nPlease add a category first before managing titles.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(text="➕ Add Category", callback_data="adm_cat_add")]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = "🎬 *Manage Titles*\n\nSelect a **Category** to view and add titles inside it:"
    markup = admin_categories_picker_keyboard(cats, prefix="adm_t_cat_pick", back_cb="adm_dash")
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_titles_in_category_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 2: Show titles inside selected category with ALWAYS VISIBLE ➕ Add Title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    cat_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    category = db.get_category(cat_id)
    cat_name = category.get("name", "Category") if category else "Category"

    titles = db.get_titles_by_category(category_id=cat_id, only_published=False)
    text = f"🎬 *Titles in:* `{cat_name}`\n\nSelect a title to manage or tap **➕ Add Title**:"
    markup = admin_titles_in_category_keyboard(
        category_id=cat_id,
        category_name=cat_name,
        titles=titles,
        page=page,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_title_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for title name inside chosen category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    cat_id = query.data.split(":")[1]
    context.user_data["title_add_cat_id"] = cat_id

    category = db.get_category(cat_id)
    cat_name = category.get("name", "Category") if category else "Category"

    await query.edit_message_text(
        f"➕ *Add Title to Category:* `{cat_name}`\n\nEnter the title name (e.g. `Solo Leveling`, `Naruto`, `Inception`):",
        reply_markup=cancel_action_keyboard(callback_data=f"adm_t_cat_pick:{cat_id}"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_NAME


async def handle_title_add_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive title name and prompt for Content Type (Normal vs Series)."""
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("⚠️ Title name cannot be empty. Try again:")
        return STATE_TITLE_ADD_NAME

    cat_id = context.user_data.get("title_add_cat_id", "")
    context.user_data["title_add_name"] = name

    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="🎬 Single Movie / Normal", callback_data="adm_t_settype:normal"),
            InlineKeyboardButton(text="📺 Web Series / Anime", callback_data="adm_t_settype:series"),
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_dash")],
    ])

    await update.message.reply_text(
        f"🎬 *Title:* `{name}`\n\nSelect the **Content Type**:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_CHOOSE_TYPE


async def handle_title_choose_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finalize title creation with selected type."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    c_type = query.data.split(":")[1]
    name = context.user_data.get("title_add_name", "Untitled")
    cat_id = context.user_data.get("title_add_cat_id", "")

    new_id = db.add_title(
        title=name,
        category_ids=[cat_id] if cat_id else [],
        content_type=c_type,
        is_published=True,
    )

    type_label = "📺 Web Series" if c_type == "series" else "🎬 Single Movie / Normal"
    await query.edit_message_text(
        f"✅ *Title Created Successfully!*\n\n"
        f"• **Title:** `{name}`\n"
        f"• **Type:** `{type_label}`\n\n"
        f"You can now manage seasons, episodes, languages, and download/watch links.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_title_detail_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View details and options for a title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    title = db.get_title(title_id)
    if not title:
        await query.answer("Title not found.", show_alert=True)
        return

    name = title.get("title", "Untitled")
    c_type = title.get("content_type", "normal")
    is_pub = title.get("is_published", True)
    kws = title.get("keywords", [])
    languages = db.get_languages_for_content(title_id=title_id)

    text = (
        f"{'📺' if c_type == 'series' else '🎬'} *Title Details*\n\n"
        f"• **Title:** `{name}`\n"
        f"• **Type:** `{'Web Series / Anime' if c_type == 'series' else 'Single Movie / Normal'}`\n"
        f"• **Status:** {'🟢 Published' if is_pub else '🔴 Unpublished'}\n"
        f"• **Languages Configured:** {', '.join(languages) if languages else 'None'}\n"
        f"• **Keywords:** {', '.join(kws) if kws else 'None'}\n"
    )
    markup = admin_title_detail_keyboard(
        title_id=title_id,
        category_id=cat_id,
        is_published=is_pub,
        is_series=(c_type == "series"),
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_title_switch_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch title between normal and series."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    title = db.get_title(title_id)
    if not title:
        return

    curr_type = title.get("content_type", "normal")
    new_type = "series" if curr_type == "normal" else "normal"
    db.edit_title(title_id, content_type=new_type)

    await query.answer(f"Switched type to {new_type}.")
    query.data = f"adm_t_v:{title_id}:{cat_id}"
    await admin_title_detail_view(update, context)


async def admin_title_toggle_publish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Publish / Unpublish title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""
    new_val = parts[3] == "1"

    db.edit_title(title_id, is_published=new_val)
    await query.answer("Publish status updated.")
    query.data = f"adm_t_v:{title_id}:{cat_id}"
    await admin_title_detail_view(update, context)


async def admin_title_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete title and its seasons/episodes/media."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    db.delete_title(title_id)
    await query.answer("Title deleted.")
    query.data = f"adm_t_cat_pick:{cat_id}" if cat_id else "adm_titles_cat"
    if cat_id:
        await admin_titles_in_category_view(update, context)
    else:
        await admin_titles_choose_category_view(update, context)


# =========================================================================
# 3. SEASONS & EPISODES MANAGEMENT (SERIES FLOW)
# =========================================================================

async def admin_seasons_list_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage seasons for a series title with ALWAYS VISIBLE ➕ Add Season."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    title = db.get_title(title_id)
    t_name = title.get("title", "Series") if title else "Series"

    seasons = db.get_seasons(title_id)
    text = f"📚 *Manage Seasons for:* `{t_name}`\n\nSelect a season to manage episodes or tap **➕ Add Season**:"
    markup = admin_seasons_keyboard(title_id=title_id, category_id=cat_id, seasons=seasons)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_season_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for season number."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    context.user_data["season_add_title_id"] = title_id
    context.user_data["season_add_cat_id"] = cat_id

    existing_seasons = db.get_seasons(title_id)
    next_num = len(existing_seasons) + 1

    await query.edit_message_text(
        f"➕ *Add Season*\n\nEnter Season Number (e.g. `{next_num}`):",
        reply_markup=cancel_action_keyboard(callback_data=f"adm_s_list:{title_id}:{cat_id}"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_SEASON_ADD_NUM


async def handle_season_add_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive season number and prompt for optional season name."""
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. 1, 2):")
        return STATE_SEASON_ADD_NUM

    context.user_data["season_add_num"] = int(text)
    await update.message.reply_text(
        f"Enter Season Name / Subtitle (or send `-` for default `Season {text}`):",
        reply_markup=cancel_action_keyboard(callback_data="adm_dash"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_SEASON_ADD_NAME


async def handle_season_add_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save season and return to season list."""
    name_input = (update.message.text or "").strip()
    s_num = context.user_data.get("season_add_num", 1)
    s_name = f"Season {s_num}" if name_input in ["-", ""] else name_input
    title_id = context.user_data.get("season_add_title_id", "")
    cat_id = context.user_data.get("season_add_cat_id", "")

    db.add_season(title_id=title_id, season_number=s_num, season_name=s_name)

    seasons = db.get_seasons(title_id)
    markup = admin_seasons_keyboard(title_id=title_id, category_id=cat_id, seasons=seasons)
    await update.message.reply_text(
        f"✅ *Added {s_name}!*",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_season_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show episodes in season with ALWAYS VISIBLE ➕ Add Episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
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
    text = (
        f"🎬 *{t_name}* ➔ `{s_name}`\n\n"
        f"Select an episode to manage languages and links or tap **➕ Add Episode**:"
    )
    markup = admin_season_detail_keyboard(
        title_id=title_id,
        season_id=season_id,
        category_id=cat_id,
        episodes=episodes,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_season_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a season."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    cat_id = parts[3] if len(parts) > 3 else ""

    db.delete_season(title_id, season_id)
    await query.answer("Season deleted.")
    query.data = f"adm_s_list:{title_id}:{cat_id}"
    await admin_seasons_list_view(update, context)


async def start_episode_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for episode number."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    cat_id = parts[3] if len(parts) > 3 else ""

    context.user_data["ep_add_title_id"] = title_id
    context.user_data["ep_add_season_id"] = season_id
    context.user_data["ep_add_cat_id"] = cat_id

    existing_episodes = db.get_episodes(title_id, season_id)
    next_num = len(existing_episodes) + 1

    await query.edit_message_text(
        f"➕ *Add Episode*\n\nEnter Episode Number (e.g. `{next_num}`):",
        reply_markup=cancel_action_keyboard(callback_data=f"adm_s_v:{title_id}:{season_id}:{cat_id}"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_EPISODE_ADD_NUM


async def handle_episode_add_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive episode number and prompt for episode title."""
    text = (update.message.text or "").strip()
    if not text.isdigit():
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. 1, 2, 3):")
        return STATE_EPISODE_ADD_NUM

    context.user_data["ep_add_num"] = int(text)
    await update.message.reply_text(
        f"Enter Episode Title (or send `-` for default `Episode {text}`):",
        reply_markup=cancel_action_keyboard(callback_data="adm_dash"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_EPISODE_ADD_NAME


async def handle_episode_add_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save episode and return to episode list."""
    name_input = (update.message.text or "").strip()
    ep_num = context.user_data.get("ep_add_num", 1)
    ep_name = f"Episode {ep_num}" if name_input in ["-", ""] else name_input

    title_id = context.user_data.get("ep_add_title_id", "")
    season_id = context.user_data.get("ep_add_season_id", "")
    cat_id = context.user_data.get("ep_add_cat_id", "")

    db.add_episode(
        title_id=title_id,
        season_id=season_id,
        episode_number=ep_num,
        episode_title=ep_name,
    )

    episodes = db.get_episodes(title_id, season_id)
    markup = admin_season_detail_keyboard(
        title_id=title_id,
        season_id=season_id,
        category_id=cat_id,
        episodes=episodes,
    )
    await update.message.reply_text(
        f"✅ *Added {ep_name}!*",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_episode_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show details for an episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
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
    )

    text = (
        f"🎬 *Episode Details*\n\n"
        f"• **Series:** `{t_name}`\n"
        f"• **Season:** `{s_name}`\n"
        f"• **Episode:** `{ep_name}`\n"
        f"• **Languages Configured:** {', '.join(languages) if languages else 'None'}\n"
    )
    markup = admin_episode_detail_keyboard(
        title_id=title_id,
        season_id=season_id,
        episode_id=episode_id,
        category_id=cat_id,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_episode_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete an episode."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    season_id = parts[2]
    episode_id = parts[3]
    cat_id = parts[4] if len(parts) > 4 else ""

    db.delete_episode(title_id, season_id, episode_id)
    await query.answer("Episode deleted.")
    query.data = f"adm_s_v:{title_id}:{season_id}:{cat_id}"
    await admin_season_view(update, context)


# =========================================================================
# 4. HIERARCHICAL LANGUAGE -> REGULATION -> LINK MANAGER
# =========================================================================

# --- A. LANGUAGES LIST & ADD ---

async def admin_content_languages_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage languages for Title or Episode with ALWAYS VISIBLE ➕ Add Language."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]  # 't' or 'e'

    if target_type == "e":
        # adm_l_list:e:title_id:season_id:episode_id:category_id
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        cat_id = parts[5] if len(parts) > 5 else ""
        target_info = {
            "title_id": title_id,
            "season_id": season_id,
            "episode_id": episode_id,
            "category_id": cat_id,
        }
        title = db.get_title(title_id)
        season = db.get_season(title_id, season_id)
        episode = db.get_episode(title_id, season_id, episode_id)
        header = f"📺 *{title.get('title', 'Series')}* ➔ *{season.get('season_name', 'Season')}* ➔ *{episode.get('episode_title', 'Episode')}*"

        languages = db.get_languages_for_content(title_id=title_id, season_id=season_id, episode_id=episode_id)
    else:
        # adm_l_list:t:title_id:category_id
        title_id = parts[2]
        cat_id = parts[3] if len(parts) > 3 else ""
        target_info = {"title_id": title_id, "category_id": cat_id}

        title = db.get_title(title_id)
        header = f"🎬 *{title.get('title', 'Title')}*"

        languages = db.get_languages_for_content(title_id=title_id)

    text = f"{header}\n\n🌐 *Language Manager*\n\nSelect a language to manage its regulations and links, or tap **➕ Add Language**:"
    markup = admin_content_languages_keyboard(
        target_type=target_type,
        target_info=target_info,
        languages=languages,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_content_language_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for language name to add."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]

    context.user_data["add_lang_type"] = target_type
    if target_type == "e":
        context.user_data["add_lang_title_id"] = parts[2]
        context.user_data["add_lang_season_id"] = parts[3]
        context.user_data["add_lang_episode_id"] = parts[4]
        context.user_data["add_lang_cat_id"] = parts[5] if len(parts) > 5 else ""
        back_cb = f"adm_l_list:e:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5] if len(parts) > 5 else ''}"
    else:
        context.user_data["add_lang_title_id"] = parts[2]
        context.user_data["add_lang_cat_id"] = parts[3] if len(parts) > 3 else ""
        back_cb = f"adm_l_list:t:{parts[2]}:{parts[3] if len(parts) > 3 else ''}"

    await query.edit_message_text(
        "➕ *Add Language*\n\nEnter the language name (e.g. `Hindi`, `Bangla`, `English`, `Japanese`, `Dual Audio`):",
        reply_markup=cancel_action_keyboard(callback_data=back_cb),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_LANG_ADD_NAME


async def handle_content_language_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save language and show regulations view."""
    lang_name = (update.message.text or "").strip()
    if not lang_name:
        await update.message.reply_text("⚠️ Language name cannot be empty. Try again:")
        return STATE_LANG_ADD_NAME

    target_type = context.user_data.get("add_lang_type", "t")
    title_id = context.user_data.get("add_lang_title_id", "")
    season_id = context.user_data.get("add_lang_season_id")
    episode_id = context.user_data.get("add_lang_episode_id")
    cat_id = context.user_data.get("add_lang_cat_id", "")

    db.add_language_to_content(
        title_id=title_id,
        language=lang_name,
        season_id=season_id,
        episode_id=episode_id,
    )

    target_info = {
        "title_id": title_id,
        "season_id": season_id or "",
        "episode_id": episode_id or "",
        "category_id": cat_id,
    }
    regulations = db.get_regulations_for_content(
        title_id=title_id,
        language=lang_name,
        season_id=season_id,
        episode_id=episode_id,
    )
    markup = admin_content_regulations_keyboard(
        target_type=target_type,
        target_info=target_info,
        language=lang_name,
        regulations=regulations,
    )

    await update.message.reply_text(
        f"✅ *Added Language:* `{lang_name}`\n\nYou can now add regulations/qualities for `{lang_name}`:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_content_language_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a language from content."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    target_type = parts[1]

    if target_type == "e":
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        lang = parts[5]
        cat_id = parts[6] if len(parts) > 6 else ""
        db.delete_language_from_content(title_id, lang, season_id=season_id, episode_id=episode_id)
        await query.answer(f"Deleted language {lang}.")
        query.data = f"adm_l_list:e:{title_id}:{season_id}:{episode_id}:{cat_id}"
    else:
        title_id = parts[2]
        lang = parts[3]
        cat_id = parts[4] if len(parts) > 4 else ""
        db.delete_language_from_content(title_id, lang)
        await query.answer(f"Deleted language {lang}.")
        query.data = f"adm_l_list:t:{title_id}:{cat_id}"

    await admin_content_languages_view(update, context)


# --- B. REGULATIONS LIST & ADD ---

async def admin_content_regulations_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage regulations for a language with ALWAYS VISIBLE ➕ Add Regulation."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]

    if target_type == "e":
        # adm_r_list:e:title_id:season_id:episode_id:language:category_id
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        language = parts[5]
        cat_id = parts[6] if len(parts) > 6 else ""
        target_info = {
            "title_id": title_id,
            "season_id": season_id,
            "episode_id": episode_id,
            "category_id": cat_id,
        }
        title = db.get_title(title_id)
        season = db.get_season(title_id, season_id)
        episode = db.get_episode(title_id, season_id, episode_id)
        header = f"📺 *{title.get('title', 'Series')}* ➔ *{season.get('season_name', 'Season')}* ➔ *{episode.get('episode_title', 'Episode')}*"

        regulations = db.get_regulations_for_content(
            title_id=title_id,
            language=language,
            season_id=season_id,
            episode_id=episode_id,
        )
    else:
        # adm_r_list:t:title_id:language:category_id
        title_id = parts[2]
        language = parts[3]
        cat_id = parts[4] if len(parts) > 4 else ""
        target_info = {"title_id": title_id, "category_id": cat_id}

        title = db.get_title(title_id)
        header = f"🎬 *{title.get('title', 'Title')}*"

        regulations = db.get_regulations_for_content(
            title_id=title_id,
            language=language,
        )

    text = (
        f"{header}\n"
        f"🗣️ *Language:* `{language}`\n\n"
        f"🎞️ *Regulation / Quality Manager*\n\n"
        f"Select a regulation to manage its streaming/download buttons, or tap **➕ Add Regulation**:"
    )
    markup = admin_content_regulations_keyboard(
        target_type=target_type,
        target_info=target_info,
        language=language,
        regulations=regulations,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_content_regulation_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for regulation name to add."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]

    context.user_data["add_reg_type"] = target_type
    if target_type == "e":
        context.user_data["add_reg_title_id"] = parts[2]
        context.user_data["add_reg_season_id"] = parts[3]
        context.user_data["add_reg_episode_id"] = parts[4]
        context.user_data["add_reg_lang"] = parts[5]
        context.user_data["add_reg_cat_id"] = parts[6] if len(parts) > 6 else ""
        back_cb = f"adm_r_list:e:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5]}:{parts[6] if len(parts) > 6 else ''}"
    else:
        context.user_data["add_reg_title_id"] = parts[2]
        context.user_data["add_reg_lang"] = parts[3]
        context.user_data["add_reg_cat_id"] = parts[4] if len(parts) > 4 else ""
        back_cb = f"adm_r_list:t:{parts[2]}:{parts[3]}:{parts[4] if len(parts) > 4 else ''}"

    lang_name = context.user_data.get("add_reg_lang", "")
    await query.edit_message_text(
        f"➕ *Add Regulation in {lang_name}*\n\n"
        f"Enter Regulation / Quality name (e.g. `2025 Regulation`, `2022 Regulation`, `1080p FHD`, `720p HD`, `480p SD`):",
        reply_markup=cancel_action_keyboard(callback_data=back_cb),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_REG_ADD_NAME


async def handle_content_regulation_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save regulation and show Links management view."""
    reg_name = (update.message.text or "").strip()
    if not reg_name:
        await update.message.reply_text("⚠️ Regulation name cannot be empty. Try again:")
        return STATE_REG_ADD_NAME

    target_type = context.user_data.get("add_reg_type", "t")
    title_id = context.user_data.get("add_reg_title_id", "")
    season_id = context.user_data.get("add_reg_season_id")
    episode_id = context.user_data.get("add_reg_episode_id")
    lang_name = context.user_data.get("add_reg_lang", "")
    cat_id = context.user_data.get("add_reg_cat_id", "")

    db.add_regulation_to_content(
        title_id=title_id,
        language=lang_name,
        regulation=reg_name,
        season_id=season_id,
        episode_id=episode_id,
    )

    target_info = {
        "title_id": title_id,
        "season_id": season_id or "",
        "episode_id": episode_id or "",
        "category_id": cat_id,
    }
    links = db.get_links_for_content(
        title_id=title_id,
        language=lang_name,
        regulation=reg_name,
        season_id=season_id,
        episode_id=episode_id,
    )
    markup = admin_content_links_keyboard(
        target_type=target_type,
        target_info=target_info,
        language=lang_name,
        regulation=reg_name,
        links=links,
    )

    await update.message.reply_text(
        f"✅ *Added Regulation:* `{reg_name}` under `{lang_name}`\n\nTap **➕ Add Link / Button** to attach URLs:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_content_regulation_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a regulation from content."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    target_type = parts[1]

    if target_type == "e":
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        lang = parts[5]
        reg = parts[6]
        cat_id = parts[7] if len(parts) > 7 else ""
        db.delete_regulation_from_content(title_id, lang, reg, season_id=season_id, episode_id=episode_id)
        await query.answer(f"Deleted regulation {reg}.")
        query.data = f"adm_r_list:e:{title_id}:{season_id}:{episode_id}:{lang}:{cat_id}"
    else:
        title_id = parts[2]
        lang = parts[3]
        reg = parts[4]
        cat_id = parts[5] if len(parts) > 5 else ""
        db.delete_regulation_from_content(title_id, lang, reg)
        await query.answer(f"Deleted regulation {reg}.")
        query.data = f"adm_r_list:t:{title_id}:{lang}:{cat_id}"

    await admin_content_regulations_view(update, context)


# --- C. LINKS & BUTTONS VIEW & ADD/DELETE ---

async def admin_content_links_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage links under a Language + Regulation with ALWAYS VISIBLE ➕ Add Link / Button."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]

    if target_type == "e":
        # adm_link_m:e:title_id:season_id:episode_id:language:regulation:category_id
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        language = parts[5]
        regulation = parts[6]
        cat_id = parts[7] if len(parts) > 7 else ""
        target_info = {
            "title_id": title_id,
            "season_id": season_id,
            "episode_id": episode_id,
            "category_id": cat_id,
        }
        title = db.get_title(title_id)
        season = db.get_season(title_id, season_id)
        episode = db.get_episode(title_id, season_id, episode_id)
        header = f"📺 *{title.get('title', 'Series')}* ➔ *{season.get('season_name', 'Season')}* ➔ *{episode.get('episode_title', 'Episode')}*"

        links = db.get_links_for_content(
            title_id=title_id,
            language=language,
            regulation=regulation,
            season_id=season_id,
            episode_id=episode_id,
        )
    else:
        # adm_link_m:t:title_id:language:regulation:category_id
        title_id = parts[2]
        language = parts[3]
        regulation = parts[4]
        cat_id = parts[5] if len(parts) > 5 else ""
        target_info = {"title_id": title_id, "category_id": cat_id}

        title = db.get_title(title_id)
        header = f"🎬 *{title.get('title', 'Title')}*"

        links = db.get_links_for_content(
            title_id=title_id,
            language=language,
            regulation=regulation,
        )

    links_text = "\n".join([f"  {idx+1}. **{l.get('label', 'Link')}:** `{l.get('url')}`" for idx, l in enumerate(links)]) or "  _No links added yet._"
    text = (
        f"{header}\n"
        f"🗣️ *Language:* `{language}`\n"
        f"🎞️ *Regulation:* `{regulation}`\n\n"
        f"🔗 *Configured Buttons & URLs ({len(links)}):*\n"
        f"{links_text}\n\n"
        f"Tap **➕ Add Link / Button** to add unlimited buttons for this combination:"
    )
    markup = admin_content_links_keyboard(
        target_type=target_type,
        target_info=target_info,
        language=language,
        regulation=regulation,
        links=links,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_content_link_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1: Prompt for Link URL."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    target_type = parts[1]

    context.user_data["lnk_add_type"] = target_type
    if target_type == "e":
        context.user_data["lnk_add_title_id"] = parts[2]
        context.user_data["lnk_add_season_id"] = parts[3]
        context.user_data["lnk_add_episode_id"] = parts[4]
        context.user_data["lnk_add_lang"] = parts[5]
        context.user_data["lnk_add_reg"] = parts[6]
        context.user_data["lnk_add_cat_id"] = parts[7] if len(parts) > 7 else ""
        back_cb = f"adm_link_m:e:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5]}:{parts[6]}:{parts[7] if len(parts) > 7 else ''}"
    else:
        context.user_data["lnk_add_title_id"] = parts[2]
        context.user_data["lnk_add_lang"] = parts[3]
        context.user_data["lnk_add_reg"] = parts[4]
        context.user_data["lnk_add_cat_id"] = parts[5] if len(parts) > 5 else ""
        back_cb = f"adm_link_m:t:{parts[2]}:{parts[3]}:{parts[4]}:{parts[5] if len(parts) > 5 else ''}"

    await query.edit_message_text(
        "➕ *Add Link / Button (Step 1/2)*\n\n"
        "Enter the destination **HTTPS / Telegram URL**\n(e.g. `https://stream.example.com` or `https://t.me/c/...`):",
        reply_markup=cancel_action_keyboard(callback_data=back_cb),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_LINK_ADD_URL


async def handle_content_link_add_url_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2: Validate URL and prompt for Button Label."""
    url = (update.message.text or "").strip()
    if not (url.startswith("http://") or url.startswith("https://") or url.startswith("tg://")):
        await update.message.reply_text("⚠️ Invalid URL. Must start with http://, https://, or tg://:")
        return STATE_LINK_ADD_URL

    context.user_data["lnk_add_url"] = url

    await update.message.reply_text(
        "➕ *Add Link / Button (Step 2/2)*\n\n"
        "Enter the **Button Label / Name**\n"
        "(e.g. `Download`, `Watch Online`, `Telegram`, `Server 1`, `Server 2` - or send `-` for default `Download`):",
        reply_markup=cancel_action_keyboard(callback_data="adm_dash"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_LINK_ADD_LABEL


async def handle_content_link_add_label_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Link & Label and return to Links view."""
    label_input = (update.message.text or "").strip()
    label = "Download" if label_input in ["-", ""] else label_input

    target_type = context.user_data.get("lnk_add_type", "t")
    title_id = context.user_data.get("lnk_add_title_id", "")
    season_id = context.user_data.get("lnk_add_season_id")
    episode_id = context.user_data.get("lnk_add_episode_id")
    lang_name = context.user_data.get("lnk_add_lang", "")
    reg_name = context.user_data.get("lnk_add_reg", "")
    url = context.user_data.get("lnk_add_url", "")
    cat_id = context.user_data.get("lnk_add_cat_id", "")

    db.add_link_to_content(
        title_id=title_id,
        language=lang_name,
        regulation=reg_name,
        url=url,
        label=label,
        season_id=season_id,
        episode_id=episode_id,
    )

    target_info = {
        "title_id": title_id,
        "season_id": season_id or "",
        "episode_id": episode_id or "",
        "category_id": cat_id,
    }
    links = db.get_links_for_content(
        title_id=title_id,
        language=lang_name,
        regulation=reg_name,
        season_id=season_id,
        episode_id=episode_id,
    )
    markup = admin_content_links_keyboard(
        target_type=target_type,
        target_info=target_info,
        language=lang_name,
        regulation=reg_name,
        links=links,
    )

    await update.message.reply_text(
        f"✅ *Button Added!*\n\n"
        f"• **Label:** `{label}`\n"
        f"• **URL:** `{url}`\n\n"
        f"Combination `{lang_name} ➔ {reg_name}` updated.",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_content_link_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a single link/button."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    target_type = parts[1]

    if target_type == "e":
        # adm_lnk_d:e:title_id:season_id:episode_id:language:regulation:link_id:category_id
        title_id = parts[2]
        season_id = parts[3]
        episode_id = parts[4]
        lang = parts[5]
        reg = parts[6]
        link_id = parts[7]
        cat_id = parts[8] if len(parts) > 8 else ""

        db.remove_link_from_content(
            title_id=title_id,
            language=lang,
            regulation=reg,
            link_id_or_url=link_id,
            season_id=season_id,
            episode_id=episode_id,
        )
        await query.answer("Link deleted.")
        query.data = f"adm_link_m:e:{title_id}:{season_id}:{episode_id}:{lang}:{reg}:{cat_id}"
    else:
        # adm_lnk_d:t:title_id:language:regulation:link_id:category_id
        title_id = parts[2]
        lang = parts[3]
        reg = parts[4]
        link_id = parts[5]
        cat_id = parts[6] if len(parts) > 6 else ""

        db.remove_link_from_content(
            title_id=title_id,
            language=lang,
            regulation=reg,
            link_id_or_url=link_id,
        )
        await query.answer("Link deleted.")
        query.data = f"adm_link_m:t:{title_id}:{lang}:{reg}:{cat_id}"

    await admin_content_links_view(update, context)


# =========================================================================
# 5. URL MANAGER (UNIFIED PATH TRAVERSAL)
# =========================================================================

async def admin_url_manager_choose_category_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """URL Manager Step 1: Select Category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cats = db.get_all_categories()
    if not cats:
        await query.edit_message_text(
            "⚠️ No Categories Found. Please add a category first.",
            reply_markup=InlineKeyboardMarkup([[back_button("adm_dash")]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    text = "🔗 *URL Manager*\n\nSelect a **Category** to browse its titles and links:"
    markup = admin_categories_picker_keyboard(cats, prefix="adm_url_cat_pick", back_cb="adm_dash")
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_url_manager_titles_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """URL Manager Step 2: Select Title in Category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    cat_id = parts[1]
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1

    category = db.get_category(cat_id)
    cat_name = category.get("name", "Category") if category else "Category"

    titles = db.get_titles_by_category(category_id=cat_id, only_published=False)
    if not titles:
        await query.edit_message_text(
            f"🔗 *URL Manager ➔ {cat_name}*\n\n⚠️ No titles found in this category.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="➕ Add Title", callback_data=f"adm_t_add:{cat_id}")],
                [back_button("adm_urls_cat")],
            ]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    keyboard = []
    for t in titles:
        t_id = str(t.get("id", ""))
        name = str(t.get("title", "Untitled"))
        c_type = t.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        # Forward directly into Title's Language/Season management
        cb = f"adm_s_list:{t_id}:{cat_id}" if c_type == "series" else f"adm_l_list:t:{t_id}:{cat_id}"
        keyboard.append([InlineKeyboardButton(text=f"{icon} {name}", callback_data=cb)])

    keyboard.append([back_button("adm_urls_cat"), InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")])

    text = f"🔗 *URL Manager ➔ {cat_name}*\n\nSelect a Title to manage its combinations and buttons:"
    await query.edit_message_text(text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


# =========================================================================
# 6. KEYWORDS & ALIASES MANAGEMENT
# =========================================================================

async def admin_keywords_choose_category_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Keywords Manager: Pick Category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cats = db.get_all_categories()
    text = "🏷️ *Keywords Manager*\n\nSelect Category to browse titles:"
    markup = admin_categories_picker_keyboard(cats, prefix="adm_kw_cat_pick", back_cb="adm_dash")
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_keywords_titles_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Keywords Manager: Select Title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cat_id = query.data.split(":")[1]
    titles = db.get_titles_by_category(category_id=cat_id, only_published=False)

    keyboard = []
    for t in titles:
        t_id = str(t.get("id", ""))
        name = str(t.get("title", "Untitled"))
        keyboard.append([InlineKeyboardButton(text=f"🏷️ {name}", callback_data=f"adm_kw_m:{t_id}:{cat_id}")])

    keyboard.append([back_button("adm_kws_cat"), InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")])
    await query.edit_message_text(
        "🏷️ *Keywords Manager*\n\nSelect a Title to add/remove search keywords:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_keywords_manage_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage keywords for a title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    title = db.get_title(title_id)
    t_name = title.get("title", "Title") if title else "Title"
    kws = title.get("keywords", []) if title else []

    text = (
        f"🏷️ *Manage Keywords for:* `{t_name}`\n\n"
        f"Current search keywords ({len(kws)}):\n"
        + ("\n".join(f"• `{k}`" for k in kws) if kws else "_None_")
    )
    markup = admin_keywords_keyboard(title_id=title_id, category_id=cat_id, keywords=kws)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def start_keyword_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for new keyword."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    cat_id = parts[2] if len(parts) > 2 else ""

    context.user_data["kw_add_title_id"] = title_id
    context.user_data["kw_add_cat_id"] = cat_id

    await query.edit_message_text(
        "🏷️ *Add Search Keyword*\n\nEnter keyword or search phrase (e.g. `season 1 hindi`, `shippuden`):",
        reply_markup=cancel_action_keyboard(callback_data=f"adm_kw_m:{title_id}:{cat_id}"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_KEYWORD


async def handle_keyword_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save keyword."""
    kw = (update.message.text or "").strip()
    title_id = context.user_data.get("kw_add_title_id", "")
    cat_id = context.user_data.get("kw_add_cat_id", "")

    if kw:
        db.add_keyword(title_id, kw)

    title = db.get_title(title_id)
    kws = title.get("keywords", []) if title else []
    markup = admin_keywords_keyboard(title_id=title_id, category_id=cat_id, keywords=kws)

    await update.message.reply_text(
        f"✅ *Keyword Added:* `{kw}`",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


async def admin_keyword_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a keyword."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    kw = parts[2]
    cat_id = parts[3] if len(parts) > 3 else ""

    db.remove_keyword(title_id, kw)
    await query.answer("Keyword removed.")
    query.data = f"adm_kw_m:{title_id}:{cat_id}"
    await admin_keywords_manage_view(update, context)


# =========================================================================
# 7. STATISTICS, USERS, REQUESTS & HELP
# =========================================================================

async def admin_stats_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display comprehensive bot statistics."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total_users = db.get_total_users()
    cats = db.get_all_categories()
    titles = db.get_all_titles()
    published = [t for t in titles if t.get("is_published", True)]
    series_cnt = len([t for t in titles if t.get("content_type") == "series"])
    movies_cnt = len(titles) - series_cnt

    text = (
        f"📊 *Bot Performance & System Statistics*\n\n"
        f"👥 **Total Registered Users:** `{total_users:,}`\n"
        f"📂 **Total Categories:** `{len(cats)}`\n"
        f"🎬 **Total Titles:** `{len(titles)}` (`{len(published)}` published)\n"
        f"   • Movies/Single: `{movies_cnt}`\n"
        f"   • Web Series/Anime: `{series_cnt}`\n"
    )
    markup = admin_stats_keyboard()
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_users_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Users overview."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total_users = db.get_total_users()
    text = (
        f"👥 *Registered User Base*\n\n"
        f"• Total users tracked in database: `{total_users:,}`"
    )
    markup = admin_users_keyboard(total_users=total_users)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_requests_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View recent media requests from users."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    reqs = db.get_recent_requests(limit=15)
    if not reqs:
        await query.edit_message_text(
            "📩 *User Requests*\n\n_No user requests received yet._",
            reply_markup=InlineKeyboardMarkup([[back_button("adm_dash")]]),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    items_text = "\n\n".join([
        f"• **From:** `{r.get('username') or r.get('user_id')}`\n  `{r.get('request_text')}`"
        for r in reqs
    ])
    text = f"📩 *Recent User Requests ({len(reqs)}):*\n\n{items_text}"
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup([[back_button("adm_dash")]]),
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_help_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt to edit bot help guide."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return ConversationHandler.END
    await query.answer()

    curr_help = db.get_help_text()
    await query.edit_message_text(
        f"📝 *Edit Bot Help Text*\n\n"
        f"Current Help Text:\n\n{curr_help}\n\n"
        f"Send the new Markdown formatted help guide text below:",
        reply_markup=cancel_action_keyboard(callback_data="adm_dash"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_HELP_EDIT_TEXT


async def handle_help_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save updated help text."""
    new_text = (update.message.text or "").strip()
    if new_text:
        db.set_help_text(new_text)

    await update.message.reply_text(
        "✅ *Help text updated successfully!*",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# HANDLER REGISTRATION
# =========================================================================

def register_admin_handlers(app: Application) -> None:
    """Register all Admin ConversationHandlers and callbacks."""

    # 1. Category Add Conversation
    cat_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_category_add_prompt, pattern=r"^adm_cat_add$")],
        states={
            STATE_CAT_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_category_add_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_cats"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(cat_add_conv)

    # 2. Title Add Conversation
    title_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_title_add_prompt, pattern=r"^adm_t_add:.+$")],
        states={
            STATE_TITLE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_add_name_input)],
            STATE_TITLE_CHOOSE_TYPE: [CallbackQueryHandler(handle_title_choose_type_callback, pattern=r"^adm_t_settype:.+$")],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(title_add_conv)

    # 3. Season Add Conversation
    season_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_season_add_prompt, pattern=r"^adm_s_add:.+$")],
        states={
            STATE_SEASON_ADD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_season_add_num_input)],
            STATE_SEASON_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_season_add_name_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(season_add_conv)

    # 4. Episode Add Conversation
    episode_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_episode_add_prompt, pattern=r"^adm_ep_add:.+$")],
        states={
            STATE_EPISODE_ADD_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_episode_add_num_input)],
            STATE_EPISODE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_episode_add_name_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(episode_add_conv)

    # 5. Language Add Conversation
    lang_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_content_language_add_prompt, pattern=r"^adm_l_add:.+$")],
        states={
            STATE_LANG_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_content_language_add_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(lang_add_conv)

    # 6. Regulation Add Conversation
    reg_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_content_regulation_add_prompt, pattern=r"^adm_r_add:.+$")],
        states={
            STATE_REG_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_content_regulation_add_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(reg_add_conv)

    # 7. Link / Button Add Conversation
    link_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_content_link_add_prompt, pattern=r"^adm_lnk_add:.+$")],
        states={
            STATE_LINK_ADD_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_content_link_add_url_input)],
            STATE_LINK_ADD_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_content_link_add_label_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(link_add_conv)

    # 8. Keyword Add Conversation
    kw_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_keyword_add_prompt, pattern=r"^adm_kw_add:.+$")],
        states={
            STATE_TITLE_ADD_KEYWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_keyword_add_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(kw_add_conv)

    # 9. Help Edit Conversation
    help_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_help_edit_prompt, pattern=r"^adm_help_edit$")],
        states={
            STATE_HELP_EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_edit_input)],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_admin_conversation, pattern=r"^adm_dash$"),
            CommandHandler("cancel", cancel_admin_conversation),
        ],
        allow_reentry=True,
    )
    app.add_handler(help_conv)

    # Base Commands & Dashboard
    app.add_handler(CommandHandler("admin", admin_start_command))
    app.add_handler(CallbackQueryHandler(admin_dashboard_callback, pattern=r"^adm_dash$"))

    # Categories
    app.add_handler(CallbackQueryHandler(admin_categories_list_view, pattern=r"^adm_cats(:\d+)?$"))
    app.add_handler(CallbackQueryHandler(admin_category_detail_view, pattern=r"^adm_cat_v:.+$"))
    app.add_handler(CallbackQueryHandler(admin_category_toggle, pattern=r"^adm_cat_t:.+$"))
    app.add_handler(CallbackQueryHandler(admin_category_delete, pattern=r"^adm_cat_d:.+$"))

    # Title Flow
    app.add_handler(CallbackQueryHandler(admin_titles_choose_category_view, pattern=r"^adm_titles_cat$"))
    app.add_handler(CallbackQueryHandler(admin_titles_in_category_view, pattern=r"^adm_t_cat_pick:.+$"))
    app.add_handler(CallbackQueryHandler(admin_title_detail_view, pattern=r"^adm_t_v:.+$"))
    app.add_handler(CallbackQueryHandler(admin_title_switch_type, pattern=r"^adm_t_sw_type:.+$"))
    app.add_handler(CallbackQueryHandler(admin_title_toggle_publish, pattern=r"^adm_t_pub:.+$"))
    app.add_handler(CallbackQueryHandler(admin_title_delete, pattern=r"^adm_t_del:.+$"))

    # Seasons & Episodes Flow
    app.add_handler(CallbackQueryHandler(admin_seasons_list_view, pattern=r"^adm_s_list:.+$"))
    app.add_handler(CallbackQueryHandler(admin_season_view, pattern=r"^adm_s_v:.+$"))
    app.add_handler(CallbackQueryHandler(admin_season_delete, pattern=r"^adm_s_del:.+$"))
    app.add_handler(CallbackQueryHandler(admin_episode_view, pattern=r"^adm_ep_v:.+$"))
    app.add_handler(CallbackQueryHandler(admin_episode_delete, pattern=r"^adm_ep_del:.+$"))

    # Hierarchical Languages, Regulations & Links
    app.add_handler(CallbackQueryHandler(admin_content_languages_view, pattern=r"^adm_l_list:.+$"))
    app.add_handler(CallbackQueryHandler(admin_content_language_delete, pattern=r"^adm_l_del:.+$"))
    app.add_handler(CallbackQueryHandler(admin_content_regulations_view, pattern=r"^adm_r_list:.+$"))
    app.add_handler(CallbackQueryHandler(admin_content_regulation_delete, pattern=r"^adm_r_del:.+$"))
    app.add_handler(CallbackQueryHandler(admin_content_links_view, pattern=r"^adm_link_m:.+$"))
    app.add_handler(CallbackQueryHandler(admin_content_link_delete, pattern=r"^adm_lnk_d:.+$"))

    # URL Manager
    app.add_handler(CallbackQueryHandler(admin_url_manager_choose_category_view, pattern=r"^adm_urls_cat$"))
    app.add_handler(CallbackQueryHandler(admin_url_manager_titles_view, pattern=r"^adm_url_cat_pick:.+$"))

    # Keywords Manager
    app.add_handler(CallbackQueryHandler(admin_keywords_choose_category_view, pattern=r"^adm_kws_cat$"))
    app.add_handler(CallbackQueryHandler(admin_keywords_titles_view, pattern=r"^adm_kw_cat_pick:.+$"))
    app.add_handler(CallbackQueryHandler(admin_keywords_manage_view, pattern=r"^adm_kw_m:.+$"))
    app.add_handler(CallbackQueryHandler(admin_keyword_remove, pattern=r"^adm_kw_rm:.+$"))

    # Stats, Users & Requests
    app.add_handler(CallbackQueryHandler(admin_stats_view, pattern=r"^adm_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users_view, pattern=r"^adm_users$"))
    app.add_handler(CallbackQueryHandler(admin_requests_view, pattern=r"^adm_reqs$"))
