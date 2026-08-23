"""
Inline Keyboards Module for Telegram Bot.

Compatible with:
- Python: 3.11+
- python-telegram-bot: >=22.0, <23.0

Provides all premium user-facing and admin InlineKeyboardMarkup generators.
Ensures short callback_data (<= 64 bytes) and native url= buttons.
"""

import math
from typing import Any, Dict, List, Optional, Union
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =========================================================================
# HELPER / COMMON BUTTONS & PAGINATION
# =========================================================================

def home_button(label: str = "🏠 Home") -> InlineKeyboardButton:
    """Return a standard Home button."""
    return InlineKeyboardButton(text=label, callback_data="nav_home")


def back_button(target_callback: str = "nav_home", label: str = "⬅️ Back") -> InlineKeyboardButton:
    """Return a back button targeting a specific callback."""
    return InlineKeyboardButton(text=label, callback_data=target_callback)


def channel_links_keyboard(
    main_link: str,
    backup_link: str,
    try_again_callback: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Keyboard prompting user to join main and backup channels."""
    keyboard = [
        [InlineKeyboardButton(text="📢 Join Main Channel", url=main_link)],
        [InlineKeyboardButton(text="🛡️ Join Backup Channel", url=backup_link)],
    ]
    if try_again_callback:
        keyboard.append([
            InlineKeyboardButton(text="🔄 Verify & Continue", callback_data=try_again_callback)
        ])
    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# USER KEYBOARDS
# =========================================================================

def user_main_menu_keyboard() -> InlineKeyboardMarkup:
    """User main landing menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Search Title", callback_data="u_search"),
            InlineKeyboardButton(text="📂 Categories", callback_data="u_cats:1"),
        ],
        [
            InlineKeyboardButton(text="🌐 Languages", callback_data="u_langs:1"),
            InlineKeyboardButton(text="ℹ️ Help & FAQ", callback_data="u_help"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def categories_keyboard(
    categories: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 8
) -> InlineKeyboardMarkup:
    """Display paginated list of categories (2 columns)."""
    total_pages = max(1, math.ceil(len(categories) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = categories[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []
    
    # 2 buttons per row
    row: List[InlineKeyboardButton] = []
    for cat in page_items:
        cat_id = str(cat.get("id", ""))
        name = str(cat.get("name", "Category"))
        row.append(InlineKeyboardButton(text=f"📁 {name}", callback_data=f"ucat:{cat_id}:1"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Pagination controls
    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"u_cats:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"u_cats:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([home_button()])
    return InlineKeyboardMarkup(keyboard)


def title_list_keyboard(
    titles: List[Dict[str, Any]],
    back_cb: str = "u_cats:1",
    page: int = 1,
    page_size: int = 6,
    prefix: str = "utitle"
) -> InlineKeyboardMarkup:
    """Display titles with pagination."""
    total_pages = max(1, math.ceil(len(titles) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = titles[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []

    for t in page_items:
        t_id = str(t.get("id", ""))
        title_name = str(t.get("title", "Untitled"))
        year = t.get("release_year")
        label = f"🎬 {title_name} ({year})" if year else f"🎬 {title_name}"
        keyboard.append([InlineKeyboardButton(text=label, callback_data=f"{prefix}:{t_id}")])

    # Navigation row
    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"{back_cb}:p{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"{back_cb}:p{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        back_button(back_cb),
        home_button()
    ])
    return InlineKeyboardMarkup(keyboard)


def search_suggestions_keyboard(
    suggestions: List[Dict[str, Any]],
    query_text: str = ""
) -> InlineKeyboardMarkup:
    """Interactive search results & suggestion buttons."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for s in suggestions[:8]:
        t_id = str(s.get("id", ""))
        title_name = str(s.get("title", "Unknown"))
        keyboard.append([
            InlineKeyboardButton(text=f"🎥 {title_name}", callback_data=f"utitle:{t_id}")
        ])

    keyboard.append([
        InlineKeyboardButton(text="🔍 Search Again", callback_data="u_search"),
        home_button()
    ])
    return InlineKeyboardMarkup(keyboard)


def languages_selection_keyboard(
    languages: List[str],
    title_id: str,
    back_cb: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Select available language for a title."""
    keyboard: List[List[InlineKeyboardButton]] = []
    
    row: List[InlineKeyboardButton] = []
    for lang in languages:
        row.append(InlineKeyboardButton(text=f"🗣️ {lang}", callback_data=f"ulang:{title_id}:{lang}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        back_button(back_cb or f"utitle:{title_id}"),
        home_button()
    ])
    return InlineKeyboardMarkup(keyboard)


def resolutions_selection_keyboard(
    resolutions: List[str],
    title_id: str,
    language: str,
    back_cb: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Select available resolution for a title + language combo."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for res in resolutions:
        row.append(InlineKeyboardButton(text=f"📺 {res}", callback_data=f"ures:{title_id}:{language}:{res}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        back_button(back_cb or f"ulang:{title_id}:{language}"),
        home_button()
    ])
    return InlineKeyboardMarkup(keyboard)


def media_actions_keyboard(
    watch_url: Optional[str] = None,
    download_url: Optional[str] = None,
    back_cb: Optional[str] = None
) -> InlineKeyboardMarkup:
    """
    Generate Watch / Download buttons using direct Telegram url= parameter.
    Includes fallback when only one or both URLs exist.
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    action_row: List[InlineKeyboardButton] = []
    if watch_url and watch_url.strip():
        action_row.append(InlineKeyboardButton(text="▶️ Watch Online", url=watch_url.strip()))
    if download_url and download_url.strip():
        action_row.append(InlineKeyboardButton(text="📥 Download Now", url=download_url.strip()))

    if action_row:
        keyboard.append(action_row)

    nav_row = [home_button()]
    if back_cb:
        nav_row.insert(0, back_button(back_cb))
    keyboard.append(nav_row)

    return InlineKeyboardMarkup(keyboard)


def user_help_keyboard() -> InlineKeyboardMarkup:
    """User help screen keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔍 Start Search", callback_data="u_search"),
            InlineKeyboardButton(text="📁 Browse Categories", callback_data="u_cats:1")
        ],
        [home_button()]
    ]
    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# ADMIN KEYBOARDS
# =========================================================================

def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Admin main control panel dashboard."""
    keyboard = [
        [
            InlineKeyboardButton(text="🎬 Titles", callback_data="adm_titles"),
            InlineKeyboardButton(text="📁 Categories", callback_data="adm_cats"),
        ],
        [
            InlineKeyboardButton(text="🗣️ Languages", callback_data="adm_langs"),
            InlineKeyboardButton(text="📺 Resolutions", callback_data="adm_resols"),
        ],
        [
            InlineKeyboardButton(text="🔗 URL Manager", callback_data="adm_urls"),
            InlineKeyboardButton(text="🏷️ Keywords", callback_data="adm_kws"),
        ],
        [
            InlineKeyboardButton(text="👥 Users", callback_data="adm_users"),
            InlineKeyboardButton(text="📊 Statistics", callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton(text="⚙️ Bot Settings", callback_data="adm_settings"),
            InlineKeyboardButton(text="📝 Help Text", callback_data="adm_help_edit"),
        ],
        [
            InlineKeyboardButton(text="🚪 Exit Admin Mode", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_categories_keyboard(
    categories: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6
) -> InlineKeyboardMarkup:
    """Admin categories management keyboard."""
    total_pages = max(1, math.ceil(len(categories) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = categories[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add New Category", callback_data="adm_cat_add")]
    ]

    for cat in page_items:
        cat_id = str(cat.get("id", ""))
        name = str(cat.get("name", "Category"))
        status = "🟢" if cat.get("is_enabled", True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(text=f"{status} {name}", callback_data=f"adm_cat_v:{cat_id}")
        ])

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_cats:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"adm_cats:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("adm_dash")])
    return InlineKeyboardMarkup(keyboard)


def admin_category_detail_keyboard(
    category_id: str,
    is_enabled: bool
) -> InlineKeyboardMarkup:
    """Individual category action keyboard."""
    toggle_text = "🔴 Disable" if is_enabled else "🟢 Enable"
    toggle_val = "0" if is_enabled else "1"

    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Edit Name", callback_data=f"adm_cat_e:{category_id}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"adm_cat_t:{category_id}:{toggle_val}"),
        ],
        [
            InlineKeyboardButton(text="🔢 Reorder Index", callback_data=f"adm_cat_o:{category_id}"),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"adm_cat_d:{category_id}"),
        ],
        [
            back_button("adm_cats"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_titles_keyboard(
    titles: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6
) -> InlineKeyboardMarkup:
    """Admin titles management list."""
    total_pages = max(1, math.ceil(len(titles) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = titles[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(text="➕ Add Title", callback_data="adm_title_add"),
            InlineKeyboardButton(text="🔍 Search Title", callback_data="adm_title_srch")
        ]
    ]

    for t in page_items:
        t_id = str(t.get("id", ""))
        title_name = str(t.get("title", "Untitled"))
        status = "🟢" if t.get("is_published", True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(text=f"{status} {title_name}", callback_data=f"adm_t_v:{t_id}")
        ])

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_titles:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"adm_titles:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([back_button("adm_dash")])
    return InlineKeyboardMarkup(keyboard)


def admin_title_detail_keyboard(
    title_id: str,
    is_published: bool
) -> InlineKeyboardMarkup:
    """Full title actions in Admin."""
    toggle_text = "🔴 Unpublish" if is_published else "🟢 Publish"
    toggle_val = "0" if is_published else "1"

    keyboard = [
        [
            InlineKeyboardButton(text="🔗 Manage URLs", callback_data=f"adm_u_m:{title_id}"),
            InlineKeyboardButton(text="📁 Categories", callback_data=f"adm_t_cat:{title_id}"),
        ],
        [
            InlineKeyboardButton(text="🏷️ Keywords", callback_data=f"adm_t_kw:{title_id}"),
            InlineKeyboardButton(text="✏️ Edit Details", callback_data=f"adm_t_edit:{title_id}"),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"adm_t_pub:{title_id}:{toggle_val}"),
            InlineKeyboardButton(text="🗑️ Delete Title", callback_data=f"adm_t_del:{title_id}"),
        ],
        [
            back_button("adm_titles"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_url_manager_keyboard(
    title_id: str,
    media_items: List[Dict[str, Any]]
) -> InlineKeyboardMarkup:
    """Admin URL combination manager for a specific title."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add URL Combination", callback_data=f"adm_u_add:{title_id}")]
    ]

    for item in media_items:
        lang = item.get("language", "Lang")
        res = item.get("resolution", "Res")
        combo_id = item.get("id", "")
        has_w = "▶️" if item.get("watch_url") else ""
        has_d = "📥" if item.get("download_url") else ""
        label = f"{lang} • {res} {has_w}{has_d}"
        keyboard.append([
            InlineKeyboardButton(text=label, callback_data=f"adm_u_v:{title_id}:{combo_id}")
        ])

    keyboard.append([
        back_button(f"adm_t_v:{title_id}"),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_media_item_detail_keyboard(
    title_id: str,
    combo_id: str,
    watch_url: Optional[str] = None,
    download_url: Optional[str] = None
) -> InlineKeyboardMarkup:
    """Edit/Delete specific media URL combination."""
    keyboard = []
    
    # Direct test buttons if urls exist
    test_row = []
    if watch_url:
        test_row.append(InlineKeyboardButton(text="▶️ Test Watch", url=watch_url))
    if download_url:
        test_row.append(InlineKeyboardButton(text="📥 Test Download", url=download_url))
    if test_row:
        keyboard.append(test_row)

    keyboard.extend([
        [
            InlineKeyboardButton(text="✏️ Update Watch URL", callback_data=f"adm_u_ew:{title_id}:{combo_id}"),
            InlineKeyboardButton(text="✏️ Update Download URL", callback_data=f"adm_u_ed:{title_id}:{combo_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑️ Delete Combination", callback_data=f"adm_u_del:{title_id}:{combo_id}")
        ],
        [
            back_button(f"adm_u_m:{title_id}"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash")
        ]
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_languages_keyboard(languages: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Admin languages management keyboard."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Language", callback_data="adm_lang_add")]
    ]

    for lang in languages:
        l_id = str(lang.get("id", ""))
        name = str(lang.get("name", "Language"))
        status = "🟢" if lang.get("is_enabled", True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(text=f"{status} {name}", callback_data=f"adm_lang_v:{l_id}")
        ])

    keyboard.append([back_button("adm_dash")])
    return InlineKeyboardMarkup(keyboard)


def admin_resolutions_keyboard(resolutions: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Admin resolutions management keyboard."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Resolution", callback_data="adm_res_add")]
    ]

    for res in resolutions:
        r_id = str(res.get("id", ""))
        name = str(res.get("name", "Resolution"))
        status = "🟢" if res.get("is_enabled", True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(text=f"{status} {name}", callback_data=f"adm_res_v:{r_id}")
        ])

    keyboard.append([back_button("adm_dash")])
    return InlineKeyboardMarkup(keyboard)


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    """Admin stats refresh and controls."""
    keyboard = [
        [
            InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="adm_stats_ref"),
            InlineKeyboardButton(text="📜 Search Logs", callback_data="adm_logs"),
        ],
        [back_button("adm_dash")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_users_keyboard(total_users: int) -> InlineKeyboardMarkup:
    """Admin users overview keyboard."""
    keyboard = [
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="adm_broadcast")],
        [back_button("adm_dash")]
    ]
    return InlineKeyboardMarkup(keyboard)


def confirmation_keyboard(
    confirm_cb: str,
    cancel_cb: str,
    confirm_text: str = "✅ Yes, Confirm",
    cancel_text: str = "❌ Cancel"
) -> InlineKeyboardMarkup:
    """Standard confirmation dialog keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_cb),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_cb),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)
