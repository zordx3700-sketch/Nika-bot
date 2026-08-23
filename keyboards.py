# FILE: keyboards.py
# CHANGE: Added 4-button user home menu + Request button, Category titles navigation, Series/Season/Episode keyboards, and Multi-URL buttons

"""
Inline Keyboards Module for Telegram Anime & Media Bot.

Compatible with:
- python-telegram-bot >=22.0, <23.0

Provides:
- User Main Menu (4 core buttons: Titles, Categories, Language, Help + 📩 Request)
- Category browsing and category-scoped title listings
- Normal & Series (Seasons, Episodes) navigation
- Multi-URL action buttons (Watch 1, Watch 2, Download 1, Download 2...) with direct external url=
- Admin Category-First Title creation & management
- Admin Series & Episode management
- Admin Multi-URL manager (Add/Delete Watch & Download URLs independently)
- Admin Keywords, Languages, Resolutions, and Analytics dashboards
"""

import math
from typing import Any, Dict, List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =========================================================================
# COMMON BUTTONS & HELPERS
# =========================================================================

def home_button(label: str = "🏠 Home") -> InlineKeyboardButton:
    """Return a standard Home navigation button."""
    return InlineKeyboardButton(text=label, callback_data="nav_home")


def back_button(target_callback: str = "nav_home", label: str = "⬅️ Back") -> InlineKeyboardButton:
    """Return a back navigation button."""
    return InlineKeyboardButton(text=label, callback_data=target_callback)


def channel_links_keyboard(
    main_link: str,
    backup_link: str,
    try_again_callback: str = "chk_membership",
) -> InlineKeyboardMarkup:
    """Keyboard prompting user to join required channels with verification."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📢 Join Main Channel", url=main_link)],
        [InlineKeyboardButton(text="🛡️ Join Backup Channel", url=backup_link)],
        [InlineKeyboardButton(text="✅ Verify Membership", callback_data=try_again_callback)],
    ])


# =========================================================================
# USER KEYBOARDS
# =========================================================================

def user_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    User home screen menu:
    Row 1: [ 🎬 Titles ] [ 📂 Categories ]
    Row 2: [ 🌐 Language ] [ ℹ️ Help ]
    Row 3: [ 📩 Request ]
    """
    keyboard = [
        [
            InlineKeyboardButton(text="🎬 Titles", callback_data="u_titles:1"),
            InlineKeyboardButton(text="📂 Categories", callback_data="u_cats:1"),
        ],
        [
            InlineKeyboardButton(text="🌐 Language", callback_data="u_langs:1"),
            InlineKeyboardButton(text="ℹ️ Help", callback_data="u_help"),
        ],
        [
            InlineKeyboardButton(text="📩 Request", callback_data="u_request"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def categories_keyboard(
    categories: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Display paginated list of categories in 2 columns."""
    total_pages = max(1, math.ceil(len(categories) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = categories[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for cat in page_items:
        cat_id = str(cat.get("id", ""))
        name = str(cat.get("name", "Category"))
        row.append(InlineKeyboardButton(text=f"📂 {name}", callback_data=f"ucat:{cat_id}:1"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Pagination row
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


def category_titles_keyboard(
    category_id: str,
    category_name: str,
    titles: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Display titles specifically belonging to the selected category."""
    total_pages = max(1, math.ceil(len(titles) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = titles[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []

    for t in page_items:
        t_id = str(t.get("id", ""))
        t_name = str(t.get("title", "Untitled"))
        c_type = t.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        keyboard.append([InlineKeyboardButton(text=f"{icon} {t_name}", callback_data=f"ut:{t_id}")])

    # Pagination row
    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"ucat:{category_id}:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"ucat:{category_id}:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        back_button("u_cats:1", label="⬅️ Categories"),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def titles_all_keyboard(
    titles: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Display all published titles with pagination."""
    total_pages = max(1, math.ceil(len(titles) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = titles[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []

    for t in page_items:
        t_id = str(t.get("id", ""))
        t_name = str(t.get("title", "Untitled"))
        c_type = t.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        keyboard.append([InlineKeyboardButton(text=f"{icon} {t_name}", callback_data=f"ut:{t_id}")])

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"u_titles:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"u_titles:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([home_button()])
    return InlineKeyboardMarkup(keyboard)


def languages_browse_keyboard(
    languages: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 8,
) -> InlineKeyboardMarkup:
    """Display languages for user discovery."""
    total_pages = max(1, math.ceil(len(languages) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = languages[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for l in page_items:
        name = l.get("name", "Language")
        row.append(InlineKeyboardButton(text=f"🗣️ {name}", callback_data=f"usrch_lang:{name}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"u_langs:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"u_langs:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([home_button()])
    return InlineKeyboardMarkup(keyboard)


def search_results_keyboard(results: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Display search results as buttons."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for r in results[:10]:
        t_id = str(r.get("id", ""))
        t_name = str(r.get("title", "Unknown"))
        c_type = r.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        keyboard.append([InlineKeyboardButton(text=f"{icon} {t_name}", callback_data=f"ut:{t_id}")])

    keyboard.append([home_button()])
    return InlineKeyboardMarkup(keyboard)


def seasons_selection_keyboard(
    title_id: str,
    seasons: List[Dict[str, Any]],
    back_cb: str = "nav_home",
) -> InlineKeyboardMarkup:
    """Display available seasons for a series title."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for s in seasons:
        s_id = str(s.get("id", ""))
        s_name = str(s.get("season_name", f"Season {s.get('season_number', 1)}"))
        row.append(InlineKeyboardButton(text=f"📚 {s_name}", callback_data=f"us_s:{title_id}:{s_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        back_button(back_cb),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def episodes_selection_keyboard(
    title_id: str,
    season_id: str,
    episodes: List[Dict[str, Any]],
    back_cb: str,
) -> InlineKeyboardMarkup:
    """Display available episodes in a season."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for ep in episodes:
        ep_id = str(ep.get("id", ""))
        ep_name = str(ep.get("episode_title", f"Episode {ep.get('episode_number', 1)}"))
        row.append(InlineKeyboardButton(text=f"🎬 {ep_name}", callback_data=f"us_ep:{title_id}:{season_id}:{ep_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        back_button(back_cb),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def languages_selection_keyboard(
    languages: List[str],
    title_id: str,
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    back_cb: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Select available language for title or episode."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for lang in languages:
        if season_id and episode_id:
            cb = f"ul:{title_id}:{season_id}:{episode_id}:{lang}"
        else:
            cb = f"ul:{title_id}:{lang}"

        row.append(InlineKeyboardButton(text=f"🗣️ {lang}", callback_data=cb))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    default_back = f"us_s:{title_id}:{season_id}" if season_id else f"ut:{title_id}"
    keyboard.append([
        back_button(back_cb or default_back),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def resolutions_selection_keyboard(
    resolutions: List[str],
    title_id: str,
    language: str,
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
    back_cb: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Select available resolution quality."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for res in resolutions:
        if season_id and episode_id:
            cb = f"ur:{title_id}:{season_id}:{episode_id}:{language}:{res}"
        else:
            cb = f"ur:{title_id}:{language}:{res}"

        row.append(InlineKeyboardButton(text=f"📺 {res}", callback_data=cb))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    default_back = f"ul:{title_id}:{season_id}:{episode_id}" if (season_id and episode_id) else f"ut:{title_id}"
    keyboard.append([
        back_button(back_cb or default_back),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def media_multi_urls_keyboard(
    watch_urls: List[str],
    download_urls: List[str],
    watch_labels: Optional[List[str]] = None,
    download_labels: Optional[List[str]] = None,
    back_cb: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Generate multiple Watch and Download buttons with direct external url= parameter.
    Each URL gets its own button without overwriting others.
    """
    keyboard: List[List[InlineKeyboardButton]] = []
    w_labels = watch_labels or []
    dl_labels = download_labels or []

    # Watch Buttons
    for idx, w_url in enumerate(watch_urls):
        if not w_url:
            continue
        custom_lbl = w_labels[idx] if idx < len(w_labels) and w_labels[idx] else ""
        if len(watch_urls) == 1:
            btn_text = f"▶️ Watch Online" if not custom_lbl else f"▶️ Watch - {custom_lbl}"
        else:
            btn_text = f"▶️ Watch - Server {idx + 1}" if not custom_lbl else f"▶️ Watch - {custom_lbl}"
        keyboard.append([InlineKeyboardButton(text=btn_text, url=w_url)])

    # Download Buttons
    for idx, dl_url in enumerate(download_urls):
        if not dl_url:
            continue
        custom_lbl = dl_labels[idx] if idx < len(dl_labels) and dl_labels[idx] else ""
        if len(download_urls) == 1:
            btn_text = f"📥 Download Now" if not custom_lbl else f"📥 Download - {custom_lbl}"
        else:
            btn_text = f"📥 Download - Server {idx + 1}" if not custom_lbl else f"📥 Download - {custom_lbl}"
        keyboard.append([InlineKeyboardButton(text=btn_text, url=dl_url)])

    # Navigation row
    nav_row = [home_button()]
    if back_cb:
        nav_row.insert(0, back_button(back_cb))
    keyboard.append(nav_row)

    return InlineKeyboardMarkup(keyboard)


def cancel_action_keyboard(callback_data: str = "nav_home", label: str = "❌ Cancel") -> InlineKeyboardMarkup:
    """Cancel conversation input button."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(text=label, callback_data=callback_data)]])


# =========================================================================
# ADMIN KEYBOARDS
# =========================================================================

def admin_dashboard_keyboard() -> InlineKeyboardMarkup:
    """Admin main dashboard menu."""
    keyboard = [
        [
            InlineKeyboardButton(text="📂 Categories", callback_data="adm_cats"),
            InlineKeyboardButton(text="🎬 Manage Titles", callback_data="adm_titles_cat"),
        ],
        [
            InlineKeyboardButton(text="🔗 URL Manager", callback_data="adm_urls_cat"),
            InlineKeyboardButton(text="🏷️ Keywords", callback_data="adm_kws_cat"),
        ],
        [
            InlineKeyboardButton(text="🌐 Languages", callback_data="adm_langs"),
            InlineKeyboardButton(text="🎞️ Resolutions", callback_data="adm_resols"),
        ],
        [
            InlineKeyboardButton(text="👥 Users", callback_data="adm_users"),
            InlineKeyboardButton(text="📊 Statistics", callback_data="adm_stats"),
        ],
        [
            InlineKeyboardButton(text="📩 User Requests", callback_data="adm_reqs"),
            InlineKeyboardButton(text="📝 Help Text", callback_data="adm_help_edit"),
        ],
        [
            InlineKeyboardButton(text="🚪 Exit Admin Panel", callback_data="nav_home"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_categories_keyboard(
    categories: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6,
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


def admin_category_detail_keyboard(category_id: str, is_enabled: bool) -> InlineKeyboardMarkup:
    """Category actions in Admin."""
    toggle_text = "🔴 Disable" if is_enabled else "🟢 Enable"
    toggle_val = "0" if is_enabled else "1"

    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Edit Name", callback_data=f"adm_cat_e:{category_id}"),
            InlineKeyboardButton(text=toggle_text, callback_data=f"adm_cat_t:{category_id}:{toggle_val}"),
        ],
        [
            InlineKeyboardButton(text="🔢 Reorder Display", callback_data=f"adm_cat_o:{category_id}"),
            InlineKeyboardButton(text="🗑️ Delete Category", callback_data=f"adm_cat_d:{category_id}"),
        ],
        [
            back_button("adm_cats"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_categories_picker_keyboard(
    categories: List[Dict[str, Any]],
    prefix: str = "adm_t_cat_pick",
    back_cb: str = "adm_dash",
) -> InlineKeyboardMarkup:
    """Picker to select a Category first before Titles or URL Manager."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for cat in categories:
        c_id = str(cat.get("id", ""))
        name = str(cat.get("name", "Category"))
        keyboard.append([InlineKeyboardButton(text=f"📂 {name}", callback_data=f"{prefix}:{c_id}")])

    keyboard.append([back_button(back_cb)])
    return InlineKeyboardMarkup(keyboard)


def admin_titles_in_category_keyboard(
    category_id: str,
    category_name: str,
    titles: List[Dict[str, Any]],
    page: int = 1,
    page_size: int = 6,
) -> InlineKeyboardMarkup:
    """Manage Titles inside a specific category."""
    total_pages = max(1, math.ceil(len(titles) / page_size))
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * page_size
    page_items = titles[start_idx : start_idx + page_size]

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"➕ Add Title in {category_name}", callback_data=f"adm_t_add:{category_id}")]
    ]

    for t in page_items:
        t_id = str(t.get("id", ""))
        title_name = str(t.get("title", "Untitled"))
        c_type = t.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        status = "🟢" if t.get("is_published", True) else "🔴"
        keyboard.append([
            InlineKeyboardButton(text=f"{status} {icon} {title_name}", callback_data=f"adm_t_v:{t_id}:{category_id}")
        ])

    nav_row: List[InlineKeyboardButton] = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_t_cat_pick:{category_id}:{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"adm_t_cat_pick:{category_id}:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([
        back_button("adm_titles_cat", label="⬅️ Categories"),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_title_detail_keyboard(
    title_id: str,
    category_id: str,
    is_published: bool,
    is_series: bool = False,
) -> InlineKeyboardMarkup:
    """Title configuration actions in Admin."""
    toggle_text = "🔴 Unpublish" if is_published else "🟢 Publish"
    toggle_val = "0" if is_published else "1"

    keyboard: List[List[InlineKeyboardButton]] = []

    if is_series:
        keyboard.append([
            InlineKeyboardButton(text="📚 Manage Seasons", callback_data=f"adm_s_list:{title_id}:{category_id}"),
            InlineKeyboardButton(text="🔗 Series URL Manager", callback_data=f"adm_u_s_m:{title_id}:{category_id}"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="🔗 Manage URLs", callback_data=f"adm_u_m:{title_id}:{category_id}"),
            InlineKeyboardButton(text="🏷️ Keywords", callback_data=f"adm_kw_m:{title_id}:{category_id}"),
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(
                text="🔄 Switch to Series" if not is_series else "🔄 Switch to Movie/Normal",
                callback_data=f"adm_t_sw_type:{title_id}:{category_id}",
            ),
            InlineKeyboardButton(text="📁 Assign Categories", callback_data=f"adm_t_cat_asg:{title_id}:{category_id}"),
        ],
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"adm_t_pub:{title_id}:{category_id}:{toggle_val}"),
            InlineKeyboardButton(text="🗑️ Delete Title", callback_data=f"adm_t_del:{title_id}:{category_id}"),
        ],
        [
            back_button(f"adm_t_cat_pick:{category_id}", label="⬅️ Category Titles"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
        ],
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_seasons_keyboard(
    title_id: str,
    category_id: str,
    seasons: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Admin seasons management for a series."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ New Season", callback_data=f"adm_s_add:{title_id}:{category_id}")]
    ]

    for s in seasons:
        s_id = str(s.get("id", ""))
        s_name = str(s.get("season_name", f"Season {s.get('season_number', 1)}"))
        keyboard.append([
            InlineKeyboardButton(text=f"📚 {s_name}", callback_data=f"adm_s_v:{title_id}:{s_id}:{category_id}")
        ])

    keyboard.append([
        back_button(f"adm_t_v:{title_id}:{category_id}"),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_season_detail_keyboard(
    title_id: str,
    season_id: str,
    category_id: str,
    episodes: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Admin episodes management for a season."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Episode", callback_data=f"adm_ep_add:{title_id}:{season_id}:{category_id}")],
        [InlineKeyboardButton(text="🗑️ Delete Season", callback_data=f"adm_s_del:{title_id}:{season_id}:{category_id}")],
    ]

    for ep in episodes:
        ep_id = str(ep.get("id", ""))
        ep_name = str(ep.get("episode_title", f"Episode {ep.get('episode_number', 1)}"))
        keyboard.append([
            InlineKeyboardButton(
                text=f"🎬 {ep_name}",
                callback_data=f"adm_ep_v:{title_id}:{season_id}:{ep_id}:{category_id}",
            )
        ])

    keyboard.append([
        back_button(f"adm_s_list:{title_id}:{category_id}"),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_episode_detail_keyboard(
    title_id: str,
    season_id: str,
    episode_id: str,
    category_id: str,
) -> InlineKeyboardMarkup:
    """Admin single episode actions."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🔗 Manage URLs for Episode",
                callback_data=f"adm_u_ep_m:{title_id}:{season_id}:{episode_id}:{category_id}",
            )
        ],
        [
            InlineKeyboardButton(
                text="🗑️ Delete Episode",
                callback_data=f"adm_ep_del:{title_id}:{season_id}:{episode_id}:{category_id}",
            )
        ],
        [
            back_button(f"adm_s_v:{title_id}:{season_id}:{category_id}"),
            InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_url_combos_list_keyboard(
    title_id: str,
    combos: List[Dict[str, Any]],
    category_id: str = "",
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """List configured URL combinations with button to add new."""
    if season_id and episode_id:
        add_cb = f"adm_u_add_ep:{title_id}:{season_id}:{episode_id}:{category_id}"
        back_cb = f"adm_ep_v:{title_id}:{season_id}:{episode_id}:{category_id}"
    else:
        add_cb = f"adm_u_add:{title_id}:{category_id}"
        back_cb = f"adm_t_v:{title_id}:{category_id}"

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add URL Combination", callback_data=add_cb)]
    ]

    for item in combos:
        lang = item.get("language", "Lang")
        res = item.get("resolution", "Res")
        w_count = len(item.get("watch_urls", []))
        dl_count = len(item.get("download_urls", []))

        label = f"{lang} • {res} (▶️{w_count} 📥{dl_count})"
        if season_id and episode_id:
            cb = f"adm_u_combo_v:{title_id}:{season_id}:{episode_id}:{lang}:{res}:{category_id}"
        else:
            cb = f"adm_u_combo_v:{title_id}:{lang}:{res}:{category_id}"

        keyboard.append([InlineKeyboardButton(text=label, callback_data=cb)])

    keyboard.append([
        back_button(back_cb),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_url_combo_manage_keyboard(
    title_id: str,
    language: str,
    resolution: str,
    combo_data: Dict[str, Any],
    category_id: str = "",
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Manage individual URLs in a combination:
    - Add Watch URL
    - Add Download URL
    - Delete specific URL links
    - Delete entire combination
    """
    keyboard: List[List[InlineKeyboardButton]] = []
    watch_urls = list(combo_data.get("watch_urls", []))
    download_urls = list(combo_data.get("download_urls", []))

    # Add URL buttons
    if season_id and episode_id:
        add_w_cb = f"adm_u_aw:{title_id}:{season_id}:{episode_id}:{language}:{resolution}:{category_id}"
        add_dl_cb = f"adm_u_adl:{title_id}:{season_id}:{episode_id}:{language}:{resolution}:{category_id}"
        del_combo_cb = f"adm_u_cdel:{title_id}:{season_id}:{episode_id}:{language}:{resolution}:{category_id}"
        back_cb = f"adm_u_ep_m:{title_id}:{season_id}:{episode_id}:{category_id}"
    else:
        add_w_cb = f"adm_u_aw:{title_id}:{language}:{resolution}:{category_id}"
        add_dl_cb = f"adm_u_adl:{title_id}:{language}:{resolution}:{category_id}"
        del_combo_cb = f"adm_u_cdel:{title_id}:{language}:{resolution}:{category_id}"
        back_cb = f"adm_u_m:{title_id}:{category_id}"

    keyboard.append([
        InlineKeyboardButton(text="➕ Add Watch URL", callback_data=add_w_cb),
        InlineKeyboardButton(text="➕ Add Download URL", callback_data=add_dl_cb),
    ])

    # Delete buttons for Watch URLs
    for idx, w_url in enumerate(watch_urls):
        preview = w_url[:24] + "..." if len(w_url) > 24 else w_url
        if season_id and episode_id:
            del_w_cb = f"adm_u_dw:{title_id}:{season_id}:{episode_id}:{language}:{resolution}:{idx}:{category_id}"
        else:
            del_w_cb = f"adm_u_dw:{title_id}:{language}:{resolution}:{idx}:{category_id}"
        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ Del Watch {idx + 1}: {preview}", callback_data=del_w_cb)
        ])

    # Delete buttons for Download URLs
    for idx, dl_url in enumerate(download_urls):
        preview = dl_url[:24] + "..." if len(dl_url) > 24 else dl_url
        if season_id and episode_id:
            del_dl_cb = f"adm_u_ddl:{title_id}:{season_id}:{episode_id}:{language}:{resolution}:{idx}:{category_id}"
        else:
            del_dl_cb = f"adm_u_ddl:{title_id}:{language}:{resolution}:{idx}:{category_id}"
        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ Del Download {idx + 1}: {preview}", callback_data=del_dl_cb)
        ])

    keyboard.append([
        InlineKeyboardButton(text="🗑️ Delete Entire Combination", callback_data=del_combo_cb)
    ])
    keyboard.append([
        back_button(back_cb),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])

    return InlineKeyboardMarkup(keyboard)


def admin_keywords_keyboard(
    title_id: str,
    category_id: str,
    keywords: List[str],
) -> InlineKeyboardMarkup:
    """Admin keywords management keyboard."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Keyword", callback_data=f"adm_kw_add:{title_id}:{category_id}")]
    ]

    for kw in keywords:
        keyboard.append([
            InlineKeyboardButton(
                text=f"🗑️ Remove: '{kw}'",
                callback_data=f"adm_kw_rm:{title_id}:{kw}:{category_id}",
            )
        ])

    keyboard.append([
        back_button(f"adm_t_v:{title_id}:{category_id}"),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
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
            InlineKeyboardButton(text=f"{status} {name}", callback_data=f"adm_lang_t:{l_id}")
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
            InlineKeyboardButton(text=f"{status} {name}", callback_data=f"adm_res_t:{r_id}")
        ])

    keyboard.append([back_button("adm_dash")])
    return InlineKeyboardMarkup(keyboard)


def admin_stats_keyboard() -> InlineKeyboardMarkup:
    """Admin statistics refresh keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🔄 Refresh Stats", callback_data="adm_stats")],
        [back_button("adm_dash")],
    ])


def admin_users_keyboard(total_users: int) -> InlineKeyboardMarkup:
    """Admin users overview keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="📢 Broadcast Announcement", callback_data="adm_broadcast")],
        [back_button("adm_dash")],
    ])


def confirmation_keyboard(
    confirm_cb: str,
    cancel_cb: str,
    confirm_text: str = "✅ Yes, Confirm",
    cancel_text: str = "❌ Cancel",
) -> InlineKeyboardMarkup:
    """Generic confirmation keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text=confirm_text, callback_data=confirm_cb),
            InlineKeyboardButton(text=cancel_text, callback_data=cancel_cb),
        ]
    ])
