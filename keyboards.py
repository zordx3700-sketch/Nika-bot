# FILE: keyboards.py
# CHANGE: Strict User Home (Categories, Help, Request), Full Hierarchical Series/Normal Flow, and Persistent Add Buttons in Admin

"""
Inline Keyboards Module for Telegram Anime & Media Bot.

Compatible with:
- python-telegram-bot >=22.0, <23.0

Provides:
- User Main Menu (Strictly: 📂 Categories, ℹ️ Help, 📩 Request)
- Category browsing and category-scoped title listings
- Normal Flow: Category -> Title -> Language -> Regulation -> URLs
- Series Flow: Category -> Title -> Season -> Episode -> Language -> Regulation -> URLs
- Multi-URL action buttons (Download, Watch, Telegram, Server 2...) with direct external URL buttons
- Admin Category-First Title creation & management
- Admin Seasons & Episodes management with persistent ➕ Add Season / ➕ Add Episode
- Admin Hierarchical Language & Regulation & Link Manager with persistent ➕ Add buttons
- Admin URL Manager with full path traversal
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
# USER KEYBOARDS (STRICT USER FLOW)
# =========================================================================

def user_main_menu_keyboard() -> InlineKeyboardMarkup:
    """
    User home screen menu:
    ONLY Categories, Help, Request.
    """
    keyboard = [
        [InlineKeyboardButton(text="📂 Categories", callback_data="u_cats:1")],
        [
            InlineKeyboardButton(text="ℹ️ Help", callback_data="u_help"),
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
        keyboard.append([InlineKeyboardButton(text=f"{icon} {t_name}", callback_data=f"ut:{t_id}:{category_id}")])

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


def search_results_keyboard(results: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Display search results as buttons."""
    keyboard: List[List[InlineKeyboardButton]] = []

    for r in results[:10]:
        t_id = str(r.get("id", ""))
        t_name = str(r.get("title", "Unknown"))
        c_type = r.get("content_type", "normal")
        icon = "📺" if c_type == "series" else "🎬"
        keyboard.append([InlineKeyboardButton(text=f"{icon} {t_name}", callback_data=f"ut:{t_id}:")])

    keyboard.append([home_button()])
    return InlineKeyboardMarkup(keyboard)


def seasons_selection_keyboard(
    title_id: str,
    seasons: List[Dict[str, Any]],
    category_id: str = "",
) -> InlineKeyboardMarkup:
    """Display available seasons for a series title."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for s in seasons:
        s_id = str(s.get("id", ""))
        s_name = str(s.get("season_name", f"Season {s.get('season_number', 1)}"))
        row.append(InlineKeyboardButton(text=f"📚 {s_name}", callback_data=f"us_s:{title_id}:{s_id}:{category_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    back_cb = f"ucat:{category_id}:1" if category_id else "u_cats:1"
    keyboard.append([
        back_button(back_cb, label="⬅️ Back"),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def episodes_selection_keyboard(
    title_id: str,
    season_id: str,
    episodes: List[Dict[str, Any]],
    category_id: str = "",
) -> InlineKeyboardMarkup:
    """Display available episodes in a season."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for ep in episodes:
        ep_id = str(ep.get("id", ""))
        ep_name = str(ep.get("episode_title", f"Episode {ep.get('episode_number', 1)}"))
        row.append(InlineKeyboardButton(text=f"🎬 {ep_name}", callback_data=f"us_ep:{title_id}:{season_id}:{ep_id}:{category_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        back_button(f"ut:{title_id}:{category_id}", label="⬅️ Seasons"),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def user_languages_keyboard(
    languages: List[str],
    title_id: str,
    category_id: str = "",
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Select available language for title or episode."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for lang in languages:
        if season_id and episode_id:
            cb = f"u_l_ep:{title_id}:{season_id}:{episode_id}:{lang}:{category_id}"
        else:
            cb = f"u_l_t:{title_id}:{lang}:{category_id}"

        row.append(InlineKeyboardButton(text=f"🗣️ {lang}", callback_data=cb))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if season_id and episode_id:
        back_cb = f"us_s:{title_id}:{season_id}:{category_id}"
    elif category_id:
        back_cb = f"ucat:{category_id}:1"
    else:
        back_cb = "u_cats:1"

    keyboard.append([
        back_button(back_cb),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def user_regulations_keyboard(
    regulations: List[str],
    title_id: str,
    language: str,
    category_id: str = "",
    season_id: Optional[str] = None,
    episode_id: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Select available regulation under a selected language."""
    keyboard: List[List[InlineKeyboardButton]] = []

    row: List[InlineKeyboardButton] = []
    for reg in regulations:
        if season_id and episode_id:
            cb = f"u_r_ep:{title_id}:{season_id}:{episode_id}:{language}:{reg}:{category_id}"
        else:
            cb = f"u_r_t:{title_id}:{language}:{reg}:{category_id}"

        row.append(InlineKeyboardButton(text=f"🎞️ {reg}", callback_data=cb))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if season_id and episode_id:
        back_cb = f"us_ep:{title_id}:{season_id}:{episode_id}:{category_id}"
    else:
        back_cb = f"ut:{title_id}:{category_id}"

    keyboard.append([
        back_button(back_cb),
        home_button(),
    ])
    return InlineKeyboardMarkup(keyboard)


def user_media_links_keyboard(
    links: List[Dict[str, Any]],
    back_cb: str = "nav_home",
) -> InlineKeyboardMarkup:
    """
    Generate interactive URL buttons for each link in Language + Regulation.
    Button text is the custom label (e.g. Download, Watch Online, Telegram, Server 2).
    """
    keyboard: List[List[InlineKeyboardButton]] = []

    for item in links:
        url = item.get("url", "").strip()
        if not url:
            continue
        label = item.get("label", "Download").strip() or "Download"

        # Add appropriate icon based on label text
        icon = "📥"
        lbl_low = label.lower()
        if "watch" in lbl_low or "stream" in lbl_low or "play" in lbl_low:
            icon = "▶️"
        elif "telegram" in lbl_low or "tg" in lbl_low:
            icon = "📢"
        elif "drive" in lbl_low or "mega" in lbl_low or "cloud" in lbl_low:
            icon = "☁️"
        elif "server" in lbl_low:
            icon = "🌐"

        btn_text = f"{icon} {label}"
        keyboard.append([InlineKeyboardButton(text=btn_text, url=url)])

    keyboard.append([
        back_button(back_cb, label="⬅️ Regulations"),
        home_button(),
    ])
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
            InlineKeyboardButton(text="🌐 Languages Preset", callback_data="adm_langs"),
            InlineKeyboardButton(text="🎞️ Regulations Preset", callback_data="adm_resols"),
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
    """Admin categories management keyboard with ALWAYS VISIBLE Add Category button."""
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
    """Picker to select a Category first."""
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
    """Manage Titles inside a category with ALWAYS VISIBLE ➕ Add Title."""
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
    """Title details actions."""
    toggle_text = "🔴 Unpublish" if is_published else "🟢 Publish"
    toggle_val = "0" if is_published else "1"

    keyboard: List[List[InlineKeyboardButton]] = []

    if is_series:
        keyboard.append([
            InlineKeyboardButton(text="📚 Manage Seasons", callback_data=f"adm_s_list:{title_id}:{category_id}"),
        ])
    else:
        keyboard.append([
            InlineKeyboardButton(text="🌐 Manage Languages", callback_data=f"adm_l_list:t:{title_id}:{category_id}"),
        ])

    keyboard.extend([
        [
            InlineKeyboardButton(text="🏷️ Keywords", callback_data=f"adm_kw_m:{title_id}:{category_id}"),
            InlineKeyboardButton(
                text="🔄 Switch to Series" if not is_series else "🔄 Switch to Normal",
                callback_data=f"adm_t_sw_type:{title_id}:{category_id}",
            ),
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


# =========================================================================
# ADMIN SEASONS & EPISODES KEYBOARDS
# =========================================================================

def admin_seasons_keyboard(
    title_id: str,
    category_id: str,
    seasons: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """Admin seasons management with ALWAYS VISIBLE ➕ Add Season."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Season", callback_data=f"adm_s_add:{title_id}:{category_id}")]
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
    """Admin episodes management with ALWAYS VISIBLE ➕ Add Episode."""
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
    """Admin single episode details."""
    keyboard = [
        [
            InlineKeyboardButton(
                text="🌐 Manage Languages",
                callback_data=f"adm_l_list:e:{title_id}:{season_id}:{episode_id}:{category_id}",
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


# =========================================================================
# ADMIN HIERARCHICAL LANGUAGE & REGULATION & LINK KEYBOARDS
# =========================================================================

def admin_content_languages_keyboard(
    target_type: str,  # 't' for title, 'e' for episode
    target_info: Dict[str, str],  # dict containing title_id, optional season_id, episode_id, category_id
    languages: List[str],
) -> InlineKeyboardMarkup:
    """
    List configured languages for Title or Episode with ALWAYS VISIBLE ➕ Add Language.
    """
    title_id = target_info.get("title_id", "")
    category_id = target_info.get("category_id", "")
    season_id = target_info.get("season_id", "")
    episode_id = target_info.get("episode_id", "")

    if target_type == "e":
        add_cb = f"adm_l_add:e:{title_id}:{season_id}:{episode_id}:{category_id}"
        back_cb = f"adm_ep_v:{title_id}:{season_id}:{episode_id}:{category_id}"
    else:
        add_cb = f"adm_l_add:t:{title_id}:{category_id}"
        back_cb = f"adm_t_v:{title_id}:{category_id}"

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Language", callback_data=add_cb)]
    ]

    for lang in languages:
        if target_type == "e":
            cb = f"adm_r_list:e:{title_id}:{season_id}:{episode_id}:{lang}:{category_id}"
        else:
            cb = f"adm_r_list:t:{title_id}:{lang}:{category_id}"
        keyboard.append([InlineKeyboardButton(text=f"🗣️ {lang}", callback_data=cb)])

    keyboard.append([
        back_button(back_cb),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_content_regulations_keyboard(
    target_type: str,
    target_info: Dict[str, str],
    language: str,
    regulations: List[str],
) -> InlineKeyboardMarkup:
    """
    List configured regulations for selected Language with ALWAYS VISIBLE ➕ Add Regulation.
    """
    title_id = target_info.get("title_id", "")
    category_id = target_info.get("category_id", "")
    season_id = target_info.get("season_id", "")
    episode_id = target_info.get("episode_id", "")

    if target_type == "e":
        add_cb = f"adm_r_add:e:{title_id}:{season_id}:{episode_id}:{language}:{category_id}"
        del_lang_cb = f"adm_l_del:e:{title_id}:{season_id}:{episode_id}:{language}:{category_id}"
        back_cb = f"adm_l_list:e:{title_id}:{season_id}:{episode_id}:{category_id}"
    else:
        add_cb = f"adm_r_add:t:{title_id}:{language}:{category_id}"
        del_lang_cb = f"adm_l_del:t:{title_id}:{language}:{category_id}"
        back_cb = f"adm_l_list:t:{title_id}:{category_id}"

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text=f"➕ Add Regulation in {language}", callback_data=add_cb)],
    ]

    for reg in regulations:
        if target_type == "e":
            cb = f"adm_link_m:e:{title_id}:{season_id}:{episode_id}:{language}:{reg}:{category_id}"
        else:
            cb = f"adm_link_m:t:{title_id}:{language}:{reg}:{category_id}"
        keyboard.append([InlineKeyboardButton(text=f"🎞️ {reg}", callback_data=cb)])

    keyboard.append([InlineKeyboardButton(text=f"🗑️ Delete Language ({language})", callback_data=del_lang_cb)])
    keyboard.append([
        back_button(back_cb),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


def admin_content_links_keyboard(
    target_type: str,
    target_info: Dict[str, str],
    language: str,
    regulation: str,
    links: List[Dict[str, Any]],
) -> InlineKeyboardMarkup:
    """
    Manage URL Links / Buttons under Language + Regulation with ALWAYS VISIBLE ➕ Add Link / Button.
    """
    title_id = target_info.get("title_id", "")
    category_id = target_info.get("category_id", "")
    season_id = target_info.get("season_id", "")
    episode_id = target_info.get("episode_id", "")

    if target_type == "e":
        add_cb = f"adm_lnk_add:e:{title_id}:{season_id}:{episode_id}:{language}:{regulation}:{category_id}"
        del_reg_cb = f"adm_r_del:e:{title_id}:{season_id}:{episode_id}:{language}:{regulation}:{category_id}"
        back_cb = f"adm_r_list:e:{title_id}:{season_id}:{episode_id}:{language}:{category_id}"
    else:
        add_cb = f"adm_lnk_add:t:{title_id}:{language}:{regulation}:{category_id}"
        del_reg_cb = f"adm_r_del:t:{title_id}:{language}:{regulation}:{category_id}"
        back_cb = f"adm_r_list:t:{title_id}:{language}:{category_id}"

    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Link / Button", callback_data=add_cb)]
    ]

    # Delete buttons for each link
    for idx, item in enumerate(links):
        link_id = item.get("id", str(idx))
        label = item.get("label", "Download")
        url = item.get("url", "")
        preview = url[:20] + "..." if len(url) > 20 else url
        if target_type == "e":
            del_link_cb = f"adm_lnk_d:e:{title_id}:{season_id}:{episode_id}:{language}:{regulation}:{link_id}:{category_id}"
        else:
            del_link_cb = f"adm_lnk_d:t:{title_id}:{language}:{regulation}:{link_id}:{category_id}"

        keyboard.append([
            InlineKeyboardButton(text=f"🗑️ Del: {label} ({preview})", callback_data=del_link_cb)
        ])

    keyboard.append([
        InlineKeyboardButton(text=f"🗑️ Delete Regulation ({regulation})", callback_data=del_reg_cb)
    ])
    keyboard.append([
        back_button(back_cb),
        InlineKeyboardButton(text="🎛️ Dashboard", callback_data="adm_dash"),
    ])
    return InlineKeyboardMarkup(keyboard)


# =========================================================================
# OTHER ADMIN KEYBOARDS
# =========================================================================

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
    """Admin global languages management."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Preset Language", callback_data="adm_lang_add")]
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
    """Admin global regulations/resolutions management."""
    keyboard: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Add Preset Regulation", callback_data="adm_res_add")]
    ]

    for res in resolutions:
        r_id = str(res.get("id", ""))
        name = str(res.get("name", "Regulation"))
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
