"""
Production-Ready Admin Control Panel Module for Telegram Bot.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0
- Firebase Firestore via DatabaseManager

Features:
- Restricted access exclusively for ADMIN_ID
- /admin entry point & interactive dashboard
- Category Management (Add, Edit name, Reorder, Toggle enable/disable, Delete)
- Title Management (Add, Edit, Category assignment, Delete, Toggle publish)
- Keyword Management (Add, Remove)
- Language Management (Add, Edit, Toggle enable/disable, Delete)
- Resolution Management (Add, Edit, Toggle enable/disable, Delete)
- URL Manager:
    Category -> Title -> Language -> Resolution -> Manage independent Watch/Download URLs
    Supports unlimited combinations without overwriting unrelated items.
- User Metrics & Search Statistics Analytics
- Broadcast messaging & Help text customization
- Full ConversationHandler flows with URL/input validation and /cancel support.
"""

import logging
import re
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
    admin_category_detail_keyboard,
    admin_dashboard_keyboard,
    admin_languages_keyboard,
    admin_media_item_detail_keyboard,
    admin_resolutions_keyboard,
    admin_stats_keyboard,
    admin_title_detail_keyboard,
    admin_titles_keyboard,
    admin_url_manager_keyboard,
    admin_users_keyboard,
    back_button,
    confirmation_keyboard,
)

logger = logging.getLogger("AdminHandlers")

# Shared Database Manager instance
db = DatabaseManager()

# Conversation states
(
    STATE_CAT_ADD,
    STATE_CAT_EDIT,
    STATE_CAT_ORDER,
    STATE_TITLE_ADD_NAME,
    STATE_TITLE_ADD_DESC,
    STATE_TITLE_ADD_YEAR,
    STATE_TITLE_EDIT,
    STATE_KW_ADD,
    STATE_KW_DEL,
    STATE_LANG_ADD,
    STATE_LANG_EDIT,
    STATE_RES_ADD,
    STATE_RES_EDIT,
    STATE_URL_WATCH_INPUT,
    STATE_URL_DOWNLOAD_INPUT,
    STATE_SETTINGS_HELP_EDIT,
    STATE_BROADCAST_INPUT,
) = range(17)


# =========================================================================
# HELPER & VALIDATION UTILITIES
# =========================================================================

def is_admin(user_id: Optional[int]) -> bool:
    """Ensure user is the configured system administrator."""
    return user_id is not None and user_id == ADMIN_ID


def is_valid_url(url_str: str) -> bool:
    """Validate HTTP/HTTPS URL format."""
    if not url_str:
        return False
    try:
        res = urlparse(url_str.strip())
        return all([res.scheme in ("http", "https"), res.netloc])
    except Exception:
        return False


def cancel_button_markup() -> InlineKeyboardMarkup:
    """Standard inline cancel markup during active conversation states."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="❌ Cancel Action", callback_data="adm_cancel_state")]
    ])


# =========================================================================
# ADMIN AUTH & DASHBOARD
# =========================================================================

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for /admin command."""
    user = update.effective_user
    if not user or not is_admin(user.id):
        if update.message:
            await update.message.reply_text("⛔ *Access Denied.* Admin authorization required.")
        return ConversationHandler.END

    text = (
        "🎛️ *Administrator Control Panel*\n\n"
        "Select a management module to configure bot content, metadata, media links, or review analytics:"
    )
    markup = admin_dashboard_keyboard()

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN
        )
    elif update.message:
        await update.message.reply_text(
            text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN
        )
    return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles /cancel command to abort any ongoing admin input prompt."""
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
# CATEGORIES MANAGEMENT
# =========================================================================

async def admin_categories_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display paginated list of categories in Admin."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    data = query.data or "adm_cats:1"
    page = 1
    if ":" in data:
        try:
            page = int(data.split(":")[1])
        except ValueError:
            page = 1

    cats = db.get_all_categories(only_enabled=False)
    markup = admin_categories_keyboard(cats, page=page, page_size=6)
    await query.edit_message_text(
        "📂 *Category Management*\n\nSelect a category to modify or add a new one:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_cat_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View and manage single category details."""
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
    """Toggle enable/disable status for category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    cat_id = parts[1]
    new_state = parts[2] == "1"
    db.set_category_enabled(cat_id, new_state)
    await query.answer(f"Category status changed to {'Enabled' if new_state else 'Disabled'}.")
    await admin_cat_view(update, context)


async def admin_cat_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a category."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    cat_id = query.data.split(":")[1]
    db.delete_category(cat_id)
    await query.answer("Category deleted successfully.")
    query.data = "adm_cats:1"
    await admin_categories_list(update, context)


# Category Add/Edit Flow Handlers
async def start_cat_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ *Add New Category*\n\nPlease enter the name of the new category:",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_ADD


async def handle_cat_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("⚠️ Invalid name. Please enter a valid text:")
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
        "✏️ *Edit Category Name*\n\nEnter the new name for this category:",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_EDIT


async def handle_cat_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    cat_id = context.user_data.get("edit_cat_id")
    if not name or not cat_id:
        await update.message.reply_text("⚠️ Invalid name. Please try again:")
        return STATE_CAT_EDIT

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
        "🔢 *Reorder Category*\n\nEnter the new integer display order (e.g. 1, 2, 10):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_CAT_ORDER


async def handle_cat_order_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    cat_id = context.user_data.get("order_cat_id")
    try:
        order_val = int(text)
    except ValueError:
        await update.message.reply_text("⚠️ Please enter a valid number (e.g. 1, 5):")
        return STATE_CAT_ORDER

    db.edit_category(cat_id, order=order_val)
    await update.message.reply_text(
        f"✅ Category display order updated to `{order_val}`.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# TITLES MANAGEMENT
# =========================================================================

async def admin_titles_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display paginated titles in Admin."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    data = query.data or "adm_titles:1"
    page = 1
    if ":" in data:
        try:
            page = int(data.split(":")[1])
        except ValueError:
            page = 1

    titles_stream = db.titles_col.order_by("updated_at", direction=db.titles_col._client.Query.DESCENDING).stream()
    all_titles = []
    for doc in titles_stream:
        d = doc.to_dict()
        d["id"] = doc.id
        all_titles.append(d)

    markup = admin_titles_keyboard(all_titles, page=page, page_size=6)
    await query.edit_message_text(
        "🎬 *Title Management*\n\nSelect a title to manage details, categories, keywords, or media URLs:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_title_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View single title control overview."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    title_id = query.data.split(":")[1]
    title = db.get_title(title_id)
    if not title:
        await query.edit_message_text("⚠️ Title not found.", reply_markup=admin_dashboard_keyboard())
        return

    status = "🟢 Published" if title.get("is_published", True) else "🔴 Draft / Unpublished"
    kws = ", ".join(title.get("keywords", [])) or "None"
    cats = title.get("category_ids", [])
    cat_names = []
    for c_id in cats:
        c_doc = db.get_category(c_id)
        if c_doc:
            cat_names.append(c_doc.get("name", c_id))
    cat_str = ", ".join(cat_names) or "Unassigned"

    media_items = db.get_media_urls_for_title(title_id)
    text = (
        f"🎬 *Title:* `{title.get('title')}`\n"
        f"• Status: {status}\n"
        f"• Release Year: `{title.get('release_year') or 'N/A'}`\n"
        f"• Categories: {cat_str}\n"
        f"• Keywords: _{kws}_\n"
        f"• Configured URL Combos: `{len(media_items)}`\n"
        f"• Description: {title.get('description') or 'None'}"
    )
    markup = admin_title_detail_keyboard(title_id, bool(title.get("is_published", True)))
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_title_toggle_pub(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle title published status."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    parts = query.data.split(":")
    title_id = parts[1]
    new_state = parts[2] == "1"
    db.edit_title(title_id, is_published=new_state)
    await query.answer(f"Title set to {'Published' if new_state else 'Draft'}.")
    await admin_title_view(update, context)


async def admin_title_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete title and all associated media URLs."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return

    title_id = query.data.split(":")[1]
    db.delete_title(title_id)
    await query.answer("Title and all media combinations deleted.")
    query.data = "adm_titles:1"
    await admin_titles_list(update, context)


# Title Add Flow Handlers
async def start_title_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "➕ *Add New Title (Step 1/3)*\n\nEnter the title name (e.g., *Naruto Shippuden*):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_NAME


async def handle_title_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = (update.message.text or "").strip()
    if not name:
        await update.message.reply_text("⚠️ Title name cannot be empty:")
        return STATE_TITLE_ADD_NAME

    context.user_data["new_title_name"] = name
    await update.message.reply_text(
        f"🎬 Title: *{name}*\n\n*(Step 2/3)* Enter a short description / synopsis (or send `-` to skip):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_DESC


async def handle_title_add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    desc = (update.message.text or "").strip()
    context.user_data["new_title_desc"] = "" if desc == "-" else desc
    await update.message.reply_text(
        "*(Step 3/3)* Enter release year (e.g. `2024` or send `-` to skip):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_TITLE_ADD_YEAR


async def handle_title_add_year(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    year_str = (update.message.text or "").strip()
    year = None
    if year_str != "-":
        try:
            year = int(year_str)
        except ValueError:
            pass

    title_name = context.user_data.get("new_title_name", "Untitled")
    desc = context.user_data.get("new_title_desc", "")

    title_id = db.add_title(
        title=title_name,
        description=desc,
        release_year=year,
        is_published=True,
    )

    await update.message.reply_text(
        f"✅ Title *{title_name}* created successfully (ID: `{title_id}`).\n\n"
        "You can now attach Category tags or configure URL combinations from URL Manager.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Category Assignment to Title
async def admin_title_assign_cats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Interactive category checkbox selector for a title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    
    if len(parts) >= 3:
        cat_to_toggle = parts[2]
        title_doc = db.get_title(title_id)
        current_cats = set(title_doc.get("category_ids", []) if title_doc else [])
        if cat_to_toggle in current_cats:
            current_cats.remove(cat_to_toggle)
        else:
            current_cats.add(cat_to_toggle)
        db.assign_categories_to_title(title_id, list(current_cats))

    title_doc = db.get_title(title_id)
    assigned_cats = set(title_doc.get("category_ids", []) if title_doc else [])

    all_cats = db.get_all_categories()
    keyboard = []
    for cat in all_cats:
        c_id = cat.get("id", "")
        c_name = cat.get("name", "Category")
        checked = "✅" if c_id in assigned_cats else "⬜"
        keyboard.append([
            InlineKeyboardButton(
                text=f"{checked} {c_name}",
                callback_data=f"adm_t_cat:{title_id}:{c_id}",
            )
        ])

    keyboard.append([
        back_button(f"adm_t_v:{title_id}", label="⬅️ Done / Back to Title")
    ])

    await query.edit_message_text(
        f"📁 *Assign Categories to:* `{title_doc.get('title') if title_doc else 'Title'}`\n\n"
        "Tap categories to toggle inclusion:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


# Keywords Add/Remove Flow
async def admin_title_keywords_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Keywords manager for title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    title_id = query.data.split(":")[1]
    title_doc = db.get_title(title_id)
    kws = title_doc.get("keywords", []) if title_doc else []

    keyboard = [
        [InlineKeyboardButton(text="➕ Add Keyword", callback_data=f"adm_kw_add:{title_id}")]
    ]
    for kw in kws:
        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ Remove: '{kw}'", callback_data=f"adm_kw_rm:{title_id}:{kw}")
        ])
    keyboard.append([back_button(f"adm_t_v:{title_id}")])

    await query.edit_message_text(
        f"🏷️ *Keywords for:* `{title_doc.get('title') if title_doc else 'Title'}`\n\n"
        f"Current: {', '.join(kws) if kws else 'None'}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_kw_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove keyword callback."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    parts = query.data.split(":")
    title_id = parts[1]
    kw = parts[2]
    db.remove_keyword(title_id, kw)
    await query.answer(f"Removed keyword '{kw}'.")
    query.data = f"adm_t_kw:{title_id}"
    await admin_title_keywords_menu(update, context)


async def start_kw_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    title_id = query.data.split(":")[1]
    context.user_data["kw_title_id"] = title_id
    await query.edit_message_text(
        "🏷️ *Add Keyword*\n\nEnter search keywords (comma-separated or single word):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_KW_ADD


async def handle_kw_add_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    title_id = context.user_data.get("kw_title_id")
    if not text or not title_id:
        return ConversationHandler.END

    for item in text.split(","):
        clean_kw = item.strip()
        if clean_kw:
            db.add_keyword(title_id, clean_kw)

    await update.message.reply_text(
        f"✅ Keywords added successfully.",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# LANGUAGES MANAGEMENT
# =========================================================================

async def admin_languages_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage supported languages."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    langs = db.get_available_languages(only_enabled=False)
    markup = admin_languages_keyboard(langs)
    await query.edit_message_text(
        "🗣️ *Language Management*\n\nConfigure available audio/subtitle languages:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_lang_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle language active state."""
    query = update.callback_query
    if not query:
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
    await query.answer()
    await query.edit_message_text(
        "➕ *Add New Language*\n\nEnter language name (e.g. `Hindi`, `English`, `Dual Audio`, `Japanese`):",
        reply_markup=cancel_button_markup(),
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


# =========================================================================
# RESOLUTIONS MANAGEMENT
# =========================================================================

async def admin_resolutions_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage supported resolutions."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    resols = db.get_available_resolutions(only_enabled=False)
    markup = admin_resolutions_keyboard(resols)
    await query.edit_message_text(
        "📺 *Resolution Management*\n\nConfigure quality options (480p, 720p, 1080p, 4K):",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_res_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle resolution active state."""
    query = update.callback_query
    if not query:
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
    await query.answer()
    await query.edit_message_text(
        "➕ *Add New Quality / Resolution*\n\nEnter resolution name (e.g. `480p`, `720p HD`, `1080p FHD`, `4K UHD`):",
        reply_markup=cancel_button_markup(),
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
# URL MANAGER (Category -> Title -> Language -> Resolution -> Links)
# =========================================================================

async def admin_url_manager_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 1: Select Category for URL Manager."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    cats = db.get_all_categories()
    keyboard = []
    for c in cats:
        keyboard.append([
            InlineKeyboardButton(
                text=f"📁 {c.get('name')}",
                callback_data=f"adm_u_cat:{c.get('id')}",
            )
        ])
    keyboard.append([back_button("adm_dash")])

    await query.edit_message_text(
        "🔗 *URL Manager (Step 1/4)*\n\nSelect category to locate the title:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_u_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 2: Select Title in Category."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    cat_id = query.data.split(":")[1]
    titles = db.get_titles_by_category(cat_id, limit=50)

    keyboard = []
    for t in titles:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎬 {t.get('title')}",
                callback_data=f"adm_u_m:{t.get('id')}",
            )
        ])
    keyboard.append([back_button("adm_urls", label="⬅️ Back to Categories")])

    await query.edit_message_text(
        "🔗 *URL Manager (Step 2/4)*\n\nSelect Title to manage URL combinations:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_url_combinations_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Step 3: View & Add URL combinations for selected title."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    title_id = query.data.split(":")[1]
    title_doc = db.get_title(title_id)
    if not title_doc:
        await query.edit_message_text("⚠️ Title not found.", reply_markup=admin_dashboard_keyboard())
        return

    media_items = db.get_media_urls_for_title(title_id)
    markup = admin_url_manager_keyboard(title_id, media_items)

    await query.edit_message_text(
        f"🔗 *URL Combinations for:* `{title_doc.get('title')}`\n\n"
        f"Configured combinations ({len(media_items)}):\n"
        "Tap a combination to view or edit URLs, or tap **➕ Add URL Combination**:",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_url_combo_detail(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View single combination details (Watch & Download URLs)."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    combo_id = parts[2]

    doc = db.titles_col.document(title_id).collection("media_items").document(combo_id).get()
    if not doc.exists:
        await query.edit_message_text("⚠️ Combination not found.")
        return

    data = doc.to_dict() or {}
    watch_url = data.get("watch_url", "")
    download_url = data.get("download_url", "")

    text = (
        f"🔗 *Combination Details*\n"
        f"• Language: `{data.get('language')}`\n"
        f"• Resolution: `{data.get('resolution')}`\n\n"
        f"▶️ *Watch URL:* `{watch_url or 'Not set'}`\n"
        f"📥 *Download URL:* `{download_url or 'Not set'}`"
    )
    markup = admin_media_item_detail_keyboard(
        title_id=title_id,
        combo_id=combo_id,
        watch_url=watch_url,
        download_url=download_url,
    )
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_url_combo_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a URL combination."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    parts = query.data.split(":")
    title_id = parts[1]
    combo_id = parts[2]

    db.titles_col.document(title_id).collection("media_items").document(combo_id).delete()
    await query.answer("Combination deleted successfully.")
    query.data = f"adm_u_m:{title_id}"
    await admin_url_combinations_view(update, context)


# Add URL Combination Wizard (Select Language -> Select Resolution -> Input URLs)
async def admin_u_add_step1_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pick Language for new URL combination."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    title_id = query.data.split(":")[1]
    langs = db.get_available_languages(only_enabled=True)

    keyboard = []
    for l in langs:
        l_name = l.get("name", "Lang")
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗣️ {l_name}",
                callback_data=f"adm_u_setlang:{title_id}:{l_name}",
            )
        ])
    keyboard.append([back_button(f"adm_u_m:{title_id}")])

    await query.edit_message_text(
        "🔗 *Add URL Combination (Step 1/2: Language)*\n\nChoose audio/subtitle language for this link:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def admin_u_add_step2_res(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pick Resolution for new URL combination."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    parts = query.data.split(":")
    title_id = parts[1]
    lang = parts[2]

    resols = db.get_available_resolutions(only_enabled=True)
    keyboard = []
    for r in resols:
        r_name = r.get("name", "Res")
        keyboard.append([
            InlineKeyboardButton(
                text=f"📺 {r_name}",
                callback_data=f"adm_u_setres:{title_id}:{lang}:{r_name}",
            )
        ])
    keyboard.append([back_button(f"adm_u_add:{title_id}")])

    await query.edit_message_text(
        f"🔗 *Add URL Combination (Step 2/2: Resolution)*\n"
        f"Language selected: `{lang}`\n\nChoose video resolution quality:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN,
    )


async def start_url_watch_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt for Watch URL input."""
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    if parts[0] == "adm_u_setres":
        # New combination creation
        context.user_data["url_title_id"] = parts[1]
        context.user_data["url_lang"] = parts[2]
        context.user_data["url_res"] = parts[3]
    elif parts[0] == "adm_u_ew":
        # Edit existing Watch URL
        title_id = parts[1]
        combo_id = parts[2]
        doc = db.titles_col.document(title_id).collection("media_items").document(combo_id).get()
        if doc.exists:
            d = doc.to_dict() or {}
            context.user_data["url_title_id"] = title_id
            context.user_data["url_lang"] = d.get("language")
            context.user_data["url_res"] = d.get("resolution")

    await query.edit_message_text(
        "▶️ *Input Watch URL (Online Streaming Link)*\n\n"
        "Send the direct HTTPS streaming / watch URL (or send `-` to skip Watch URL):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_URL_WATCH_INPUT


async def handle_url_watch_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text != "-" and not is_valid_url(text):
        await update.message.reply_text("⚠️ Invalid URL format. Must start with http:// or https:// (or send `-` to skip):")
        return STATE_URL_WATCH_INPUT

    context.user_data["watch_url_val"] = "" if text == "-" else text
    await update.message.reply_text(
        "📥 *Input Download URL*\n\n"
        "Send the direct HTTPS download URL (or send `-` to skip Download URL):",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_URL_DOWNLOAD_INPUT


async def handle_url_download_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text != "-" and not is_valid_url(text):
        await update.message.reply_text("⚠️ Invalid URL format. Must start with http:// or https:// (or send `-` to skip):")
        return STATE_URL_DOWNLOAD_INPUT

    download_val = "" if text == "-" else text
    watch_val = context.user_data.get("watch_url_val", "")

    title_id = context.user_data.get("url_title_id")
    lang = context.user_data.get("url_lang")
    res = context.user_data.get("url_res")

    if not title_id or not lang or not res:
        await update.message.reply_text("⚠️ Session expired. Please retry from URL Manager.")
        return ConversationHandler.END

    db.set_media_url(
        title_id=title_id,
        language=lang,
        resolution=res,
        watch_url=watch_val,
        download_url=download_val,
    )

    await update.message.reply_text(
        f"✅ *Media Combination Saved!*\n\n"
        f"• Language: `{lang}`\n"
        f"• Quality: `{res}`\n"
        f"• Watch URL: `{watch_val or 'None'}`\n"
        f"• Download URL: `{download_val or 'None'}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# =========================================================================
# USERS & STATISTICS
# =========================================================================

async def admin_stats_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View bot usage statistics and popular search queries."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total_users = db.get_total_users()
    top_kws = db.get_top_searched_keywords(limit=8)
    kw_lines = []
    for idx, item in enumerate(top_kws, 1):
        kw_lines.append(f"{idx}. `{item['keyword']}` ({item['count']} searches)")
    kw_str = "\n".join(kw_lines) or "No search history recorded yet."

    text = (
        "📊 *Bot Analytics & Statistics*\n\n"
        f"👥 *Total Registered Users:* `{total_users}`\n\n"
        f"🔥 *Top Searched Queries:*\n{kw_str}"
    )
    markup = admin_stats_keyboard()
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.MARKDOWN)


async def admin_users_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View registered users overview."""
    query = update.callback_query
    if not query or not is_admin(update.effective_user.id if update.effective_user else None):
        return
    await query.answer()

    total = db.get_total_users()
    markup = admin_users_keyboard(total)
    await query.edit_message_text(
        f"👥 *Users Management*\n\nTotal registered members: `{total}`",
        reply_markup=markup,
        parse_mode=ParseMode.MARKDOWN,
    )


# Broadcast message flow
async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📢 *Broadcast Announcement*\n\n"
        "Send the message text you wish to broadcast to all registered users:",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_BROADCAST_INPUT


async def handle_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if not text:
        return STATE_BROADCAST_INPUT

    status_msg = await update.message.reply_text("⏳ *Broadcasting message...*", parse_mode=ParseMode.MARKDOWN)
    success_count = 0
    fail_count = 0

    for user_doc in db.users_col.stream():
        u_data = user_doc.to_dict()
        uid = u_data.get("user_id")
        if uid:
            try:
                await context.bot.send_message(chat_id=uid, text=text, parse_mode=ParseMode.MARKDOWN)
                success_count += 1
            except Exception:
                fail_count += 1

    await status_msg.edit_text(
        f"📢 *Broadcast Complete!*\n\n"
        f"✅ Delivered: `{success_count}`\n"
        f"❌ Failed: `{fail_count}`",
        reply_markup=admin_dashboard_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ConversationHandler.END


# Help Text Editor Flow
async def start_help_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    curr_help = db.get_help_text()
    await query.edit_message_text(
        f"📝 *Edit Bot Help Text*\n\nCurrent help text:\n_{curr_help}_\n\n"
        "Send the new formatted Markdown help text:",
        reply_markup=cancel_button_markup(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return STATE_SETTINGS_HELP_EDIT


async def handle_help_edit_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    if text:
        db.set_help_text(text)
        await update.message.reply_text(
            "✅ *Help text updated successfully.*",
            reply_markup=admin_dashboard_keyboard(),
            parse_mode=ParseMode.MARKDOWN,
        )
    return ConversationHandler.END


# =========================================================================
# ADMIN CONVERSATION & HANDLER REGISTRATION
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
            CallbackQueryHandler(start_title_add, pattern="^adm_title_add$"),
            CallbackQueryHandler(start_kw_add, pattern="^adm_kw_add:"),
            CallbackQueryHandler(start_lang_add, pattern="^adm_lang_add$"),
            CallbackQueryHandler(start_res_add, pattern="^adm_res_add$"),
            CallbackQueryHandler(start_url_watch_input, pattern="^(adm_u_setres|adm_u_ew):"),
            CallbackQueryHandler(start_broadcast, pattern="^adm_broadcast$"),
            CallbackQueryHandler(start_help_edit, pattern="^adm_help_edit$"),
        ],
        states={
            STATE_CAT_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_add_input)],
            STATE_CAT_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_edit_input)],
            STATE_CAT_ORDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cat_order_input)],
            STATE_TITLE_ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_add_name)],
            STATE_TITLE_ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_add_desc)],
            STATE_TITLE_ADD_YEAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_title_add_year)],
            STATE_KW_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_kw_add_input)],
            STATE_LANG_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lang_add_input)],
            STATE_RES_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_res_add_input)],
            STATE_URL_WATCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_watch_input)],
            STATE_URL_DOWNLOAD_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url_download_input)],
            STATE_BROADCAST_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_input)],
            STATE_SETTINGS_HELP_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_edit_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(cancel_command, pattern="^adm_cancel_state$"),
            CallbackQueryHandler(admin_command, pattern="^adm_dash$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(admin_conv)

    # Categories callbacks
    app.add_handler(CallbackQueryHandler(admin_categories_list, pattern="^adm_cats"))
    app.add_handler(CallbackQueryHandler(admin_cat_view, pattern="^adm_cat_v:"))
    app.add_handler(CallbackQueryHandler(admin_cat_toggle, pattern="^adm_cat_t:"))
    app.add_handler(CallbackQueryHandler(admin_cat_delete, pattern="^adm_cat_d:"))

    # Titles callbacks
    app.add_handler(CallbackQueryHandler(admin_titles_list, pattern="^adm_titles"))
    app.add_handler(CallbackQueryHandler(admin_title_view, pattern="^adm_t_v:"))
    app.add_handler(CallbackQueryHandler(admin_title_toggle_pub, pattern="^adm_t_pub:"))
    app.add_handler(CallbackQueryHandler(admin_title_delete, pattern="^adm_t_del:"))
    app.add_handler(CallbackQueryHandler(admin_title_assign_cats, pattern="^adm_t_cat:"))
    app.add_handler(CallbackQueryHandler(admin_title_keywords_menu, pattern="^adm_t_kw:"))
    app.add_handler(CallbackQueryHandler(admin_kw_remove, pattern="^adm_kw_rm:"))

    # Languages callbacks
    app.add_handler(CallbackQueryHandler(admin_languages_list, pattern="^adm_langs$"))
    app.add_handler(CallbackQueryHandler(admin_lang_toggle, pattern="^adm_lang_v:"))

    # Resolutions callbacks
    app.add_handler(CallbackQueryHandler(admin_resolutions_list, pattern="^adm_resols$"))
    app.add_handler(CallbackQueryHandler(admin_res_toggle, pattern="^adm_res_v:"))

    # URL Manager callbacks
    app.add_handler(CallbackQueryHandler(admin_url_manager_entry, pattern="^adm_urls$"))
    app.add_handler(CallbackQueryHandler(admin_u_cat_selected, pattern="^adm_u_cat:"))
    app.add_handler(CallbackQueryHandler(admin_url_combinations_view, pattern="^adm_u_m:"))
    app.add_handler(CallbackQueryHandler(admin_url_combo_detail, pattern="^adm_u_v:"))
    app.add_handler(CallbackQueryHandler(admin_url_combo_delete, pattern="^adm_u_del:"))
    app.add_handler(CallbackQueryHandler(admin_u_add_step1_lang, pattern="^adm_u_add:"))
    app.add_handler(CallbackQueryHandler(admin_u_add_step2_res, pattern="^adm_u_setlang:"))

    # Users & Stats callbacks
    app.add_handler(CallbackQueryHandler(admin_stats_view, pattern="^adm_stats"))
    app.add_handler(CallbackQueryHandler(admin_users_view, pattern="^adm_users$"))
