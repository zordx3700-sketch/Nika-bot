"""
Production-Ready Firebase Firestore Database Manager.

Features supported:
- USERS: register_user, get_user, get_total_users
- CATEGORIES: add, edit, delete, enable/disable, reorder, get all
- TITLES: add, edit, delete, get, category assignment
- KEYWORDS: add, remove, search by keyword
- LANGUAGES: add, edit, delete, enable/disable, get available languages
- RESOLUTIONS: add, edit, delete, enable/disable, get available resolutions
- MEDIA URLS: title + language + resolution combinations (watch_url and download_url independent)
- SEARCH: exact title, partial title, keyword, alias, suggestions
- SETTINGS: help text, bot settings
- SEARCH LOGS: user, keyword, result, timestamp
"""

import os
import json
import base64
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger("DatabaseManager")


def _get_firestore_client() -> firestore.firestore.Client:
    """Initialize Firebase Admin with FIREBASE_CREDENTIALS_B64 if not already initialized."""
    if not firebase_admin._apps:
        b64_creds = os.environ.get("FIREBASE_CREDENTIALS_B64", "").strip()
        if not b64_creds:
            raise ValueError("FIREBASE_CREDENTIALS_B64 environment variable is missing or empty.")
        
        try:
            decoded_bytes = base64.b64decode(b64_creds)
            cred_dict = json.loads(decoded_bytes.decode("utf-8"))
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized in DatabaseManager.")
        except Exception as e:
            logger.error("Failed to initialize Firebase Admin in DatabaseManager: %s", e)
            raise

    return firestore.client()


class DatabaseManager:
    """Production Firestore Database Manager for Telegram Bot."""

    def __init__(self, db_client: Optional[firestore.firestore.Client] = None):
        self.db: firestore.firestore.Client = db_client or _get_firestore_client()
        
        # Collection references
        self.users_col = self.db.collection("users")
        self.categories_col = self.db.collection("categories")
        self.titles_col = self.db.collection("titles")
        self.languages_col = self.db.collection("languages")
        self.resolutions_col = self.db.collection("resolutions")
        self.settings_col = self.db.collection("settings")
        self.search_logs_col = self.db.collection("search_logs")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    # =========================================================================
    # USERS
    # =========================================================================

    def register_user(
        self,
        user_id: Union[int, str],
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a new user or update existing user activity info."""
        doc_ref = self.users_col.document(str(user_id))
        doc = doc_ref.get()

        data: Dict[str, Any] = {
            "user_id": int(user_id),
            "username": username or "",
            "first_name": first_name or "",
            "last_name": last_name or "",
            "language_code": language_code or "",
            "last_active_at": self._now(),
        }

        if not doc.exists:
            data["created_at"] = self._now()
            data["is_banned"] = False
            doc_ref.set(data)
            logger.info("Registered new user: %s", user_id)
        else:
            doc_ref.update(data)

        user_data = doc_ref.get().to_dict() or {}
        return user_data

    def get_user(self, user_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Retrieve user document by Telegram user ID."""
        doc = self.users_col.document(str(user_id)).get()
        if doc.exists:
            res = doc.to_dict()
            res["id"] = doc.id
            return res
        return None

    def get_total_users(self) -> int:
        """Count total registered users."""
        count_query = self.users_col.count()
        results = count_query.get()
        return int(results[0][0].value)

    # =========================================================================
    # CATEGORIES
    # =========================================================================

    def add_category(self, name: str, order: int = 0, is_enabled: bool = True) -> str:
        """Add a new category."""
        data = {
            "name": name.strip(),
            "name_lower": name.strip().lower(),
            "order": int(order),
            "is_enabled": bool(is_enabled),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        _, doc_ref = self.categories_col.add(data)
        logger.info("Added category: %s (%s)", name, doc_ref.id)
        return doc_ref.id

    def edit_category(
        self,
        category_id: str,
        name: Optional[str] = None,
        order: Optional[int] = None,
        is_enabled: Optional[bool] = None
    ) -> bool:
        """Edit category properties."""
        doc_ref = self.categories_col.document(category_id)
        if not doc_ref.get().exists:
            return False

        update_data: Dict[str, Any] = {"updated_at": self._now()}
        if name is not None:
            update_data["name"] = name.strip()
            update_data["name_lower"] = name.strip().lower()
        if order is not None:
            update_data["order"] = int(order)
        if is_enabled is not None:
            update_data["is_enabled"] = bool(is_enabled)

        doc_ref.update(update_data)
        return True

    def delete_category(self, category_id: str) -> bool:
        """Delete category by ID."""
        doc_ref = self.categories_col.document(category_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        logger.info("Deleted category: %s", category_id)
        return True

    def set_category_enabled(self, category_id: str, is_enabled: bool) -> bool:
        """Enable or disable category."""
        return self.edit_category(category_id, is_enabled=is_enabled)

    def reorder_categories(self, category_orders: Dict[str, int]) -> None:
        """
        Batch update display orders for categories.
        :param category_orders: Dict where key is category_id and value is order int
        """
        batch = self.db.batch()
        for cat_id, order in category_orders.items():
            doc_ref = self.categories_col.document(cat_id)
            batch.update(doc_ref, {"order": int(order), "updated_at": self._now()})
        batch.commit()

    def get_all_categories(self, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """Get all categories sorted by order."""
        query = self.categories_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))
        
        docs = query.order_by("order").stream()
        categories = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            categories.append(item)
        return categories

    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get single category by ID."""
        doc = self.categories_col.document(category_id).get()
        if doc.exists:
            item = doc.to_dict()
            item["id"] = doc.id
            return item
        return None

    # =========================================================================
    # LANGUAGES
    # =========================================================================

    def add_language(self, name: str, code: str = "", order: int = 0, is_enabled: bool = True) -> str:
        """Add a new supported audio/sub language."""
        data = {
            "name": name.strip(),
            "code": code.strip().lower() or name.strip().lower(),
            "order": int(order),
            "is_enabled": bool(is_enabled),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        _, doc_ref = self.languages_col.add(data)
        return doc_ref.id

    def edit_language(
        self,
        language_id: str,
        name: Optional[str] = None,
        code: Optional[str] = None,
        order: Optional[int] = None,
        is_enabled: Optional[bool] = None
    ) -> bool:
        """Edit language details."""
        doc_ref = self.languages_col.document(language_id)
        if not doc_ref.get().exists:
            return False

        update_data: Dict[str, Any] = {"updated_at": self._now()}
        if name is not None:
            update_data["name"] = name.strip()
        if code is not None:
            update_data["code"] = code.strip().lower()
        if order is not None:
            update_data["order"] = int(order)
        if is_enabled is not None:
            update_data["is_enabled"] = bool(is_enabled)

        doc_ref.update(update_data)
        return True

    def delete_language(self, language_id: str) -> bool:
        """Delete language by ID."""
        doc_ref = self.languages_col.document(language_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def set_language_enabled(self, language_id: str, is_enabled: bool) -> bool:
        """Enable or disable a language."""
        return self.edit_language(language_id, is_enabled=is_enabled)

    def get_available_languages(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        """Get all languages ordered by preference."""
        query = self.languages_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))
        
        docs = query.order_by("order").stream()
        languages = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            languages.append(item)
        return languages

    # =========================================================================
    # RESOLUTIONS
    # =========================================================================

    def add_resolution(self, name: str, order: int = 0, is_enabled: bool = True) -> str:
        """Add a video quality resolution (e.g., 480p, 720p, 1080p, 4K)."""
        data = {
            "name": name.strip(),
            "order": int(order),
            "is_enabled": bool(is_enabled),
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        _, doc_ref = self.resolutions_col.add(data)
        return doc_ref.id

    def edit_resolution(
        self,
        resolution_id: str,
        name: Optional[str] = None,
        order: Optional[int] = None,
        is_enabled: Optional[bool] = None
    ) -> bool:
        """Edit resolution parameters."""
        doc_ref = self.resolutions_col.document(resolution_id)
        if not doc_ref.get().exists:
            return False

        update_data: Dict[str, Any] = {"updated_at": self._now()}
        if name is not None:
            update_data["name"] = name.strip()
        if order is not None:
            update_data["order"] = int(order)
        if is_enabled is not None:
            update_data["is_enabled"] = bool(is_enabled)

        doc_ref.update(update_data)
        return True

    def delete_resolution(self, resolution_id: str) -> bool:
        """Delete resolution."""
        doc_ref = self.resolutions_col.document(resolution_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def set_resolution_enabled(self, resolution_id: str, is_enabled: bool) -> bool:
        """Enable or disable a resolution."""
        return self.edit_resolution(resolution_id, is_enabled=is_enabled)

    def get_available_resolutions(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        """Get all video resolutions ordered by specification."""
        query = self.resolutions_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))
        
        docs = query.order_by("order").stream()
        resolutions = []
        for doc in docs:
            item = doc.to_dict()
            item["id"] = doc.id
            resolutions.append(item)
        return resolutions

    # =========================================================================
    # TITLES & CATEGORY ASSIGNMENT
    # =========================================================================

    def add_title(
        self,
        title: str,
        category_ids: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        poster_url: str = "",
        description: str = "",
        release_year: Optional[int] = None,
        is_published: bool = True
    ) -> str:
        """
        Add a new media title.
        Generates search tokens for flexible partial search and suggestions.
        """
        t_clean = title.strip()
        kw_list = [k.strip().lower() for k in (keywords or []) if k.strip()]
        al_list = [a.strip() for a in (aliases or []) if a.strip()]
        
        # Build search tokens
        search_tokens = set()
        search_tokens.add(t_clean.lower())
        for word in t_clean.lower().split():
            search_tokens.add(word)
        for kw in kw_list:
            search_tokens.add(kw)
            for kw_word in kw.split():
                search_tokens.add(kw_word)
        for al in al_list:
            search_tokens.add(al.lower())
            for al_word in al.lower().split():
                search_tokens.add(al_word)

        data = {
            "title": t_clean,
            "title_lower": t_clean.lower(),
            "category_ids": category_ids or [],
            "keywords": kw_list,
            "aliases": al_list,
            "search_tokens": list(search_tokens),
            "poster_url": poster_url.strip(),
            "description": description.strip(),
            "release_year": release_year,
            "is_published": bool(is_published),
            "view_count": 0,
            "created_at": self._now(),
            "updated_at": self._now(),
        }

        _, doc_ref = self.titles_col.add(data)
        logger.info("Added title: %s (%s)", t_clean, doc_ref.id)
        return doc_ref.id

    def edit_title(
        self,
        title_id: str,
        title: Optional[str] = None,
        category_ids: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        poster_url: Optional[str] = None,
        description: Optional[str] = None,
        release_year: Optional[int] = None,
        is_published: Optional[bool] = None
    ) -> bool:
        """Edit an existing title details and regenerate search indices."""
        doc_ref = self.titles_col.document(title_id)
        existing = doc_ref.get()
        if not existing.exists:
            return False

        existing_data = existing.to_dict() or {}
        update_data: Dict[str, Any] = {"updated_at": self._now()}

        curr_title = title.strip() if title is not None else existing_data.get("title", "")
        curr_keywords = (
            [k.strip().lower() for k in keywords if k.strip()]
            if keywords is not None
            else existing_data.get("keywords", [])
        )
        curr_aliases = (
            [a.strip() for a in aliases if a.strip()]
            if aliases is not None
            else existing_data.get("aliases", [])
        )

        if title is not None:
            update_data["title"] = curr_title
            update_data["title_lower"] = curr_title.lower()

        if category_ids is not None:
            update_data["category_ids"] = category_ids

        if keywords is not None:
            update_data["keywords"] = curr_keywords

        if aliases is not None:
            update_data["aliases"] = curr_aliases

        if poster_url is not None:
            update_data["poster_url"] = poster_url.strip()

        if description is not None:
            update_data["description"] = description.strip()

        if release_year is not None:
            update_data["release_year"] = release_year

        if is_published is not None:
            update_data["is_published"] = bool(is_published)

        # Re-compute search tokens
        search_tokens = set()
        search_tokens.add(curr_title.lower())
        for word in curr_title.lower().split():
            search_tokens.add(word)
        for kw in curr_keywords:
            search_tokens.add(kw)
            for kw_word in kw.split():
                search_tokens.add(kw_word)
        for al in curr_aliases:
            search_tokens.add(al.lower())
            for al_word in al.lower().split():
                search_tokens.add(al_word)

        update_data["search_tokens"] = list(search_tokens)
        doc_ref.update(update_data)
        return True

    def delete_title(self, title_id: str) -> bool:
        """Delete a title and all its media URL combinations."""
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False

        # Delete media combinations subcollection
        media_col = doc_ref.collection("media_items")
        media_docs = media_col.stream()
        batch = self.db.batch()
        for m_doc in media_docs:
            batch.delete(m_doc.reference)
        batch.commit()

        # Delete title document
        doc_ref.delete()
        logger.info("Deleted title: %s", title_id)
        return True

    def get_title(self, title_id: str) -> Optional[Dict[str, Any]]:
        """Get single title by document ID."""
        doc = self.titles_col.document(title_id).get()
        if doc.exists:
            item = doc.to_dict()
            item["id"] = doc.id
            return item
        return None

    def assign_categories_to_title(self, title_id: str, category_ids: List[str]) -> bool:
        """Assign category IDs to title."""
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.update({
            "category_ids": category_ids,
            "updated_at": self._now()
        })
        return True

    def get_titles_by_category(self, category_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch published titles under a specific category."""
        query = (
            self.titles_col
            .where(filter=FieldFilter("category_ids", "array_contains", category_id))
            .where(filter=FieldFilter("is_published", "==", True))
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            item = doc.to_dict()
            item["id"] = doc.id
            results.append(item)
        return results

    # =========================================================================
    # KEYWORDS & ALIASES
    # =========================================================================

    def add_keyword(self, title_id: str, keyword: str) -> bool:
        """Add a search keyword to title."""
        kw = keyword.strip().lower()
        if not kw:
            return False

        doc_ref = self.titles_col.document(title_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        kws = set(data.get("keywords", []))
        kws.add(kw)
        return self.edit_title(title_id, keywords=list(kws))

    def remove_keyword(self, title_id: str, keyword: str) -> bool:
        """Remove a search keyword from title."""
        kw = keyword.strip().lower()
        doc_ref = self.titles_col.document(title_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        kws = [k for k in data.get("keywords", []) if k != kw]
        return self.edit_title(title_id, keywords=kws)

    def search_by_keyword(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search titles by exact or contains keyword."""
        kw = keyword.strip().lower()
        if not kw:
            return []

        query = (
            self.titles_col
            .where(filter=FieldFilter("keywords", "array_contains", kw))
            .where(filter=FieldFilter("is_published", "==", True))
            .limit(limit)
        )
        results = []
        for doc in query.stream():
            item = doc.to_dict()
            item["id"] = doc.id
            results.append(item)
        return results

    # =========================================================================
    # MEDIA URLS (title + language + resolution combinations)
    # =========================================================================

    @staticmethod
    def _make_combo_id(language: str, resolution: str) -> str:
        """Generate a clean deterministic document ID for combinations."""
        clean_lang = "".join(c if c.isalnum() else "_" for c in language.strip().lower())
        clean_res = "".join(c if c.isalnum() else "_" for c in resolution.strip().lower())
        return f"{clean_lang}__{clean_res}"

    def set_media_url(
        self,
        title_id: str,
        language: str,
        resolution: str,
        watch_url: Optional[str] = None,
        download_url: Optional[str] = None,
        file_size: str = "",
        extra_note: str = ""
    ) -> bool:
        """
        Add or update a media URL combination for title + language + resolution.
        Stores watch_url and download_url independently without overwriting the other
        if not provided.
        """
        title_ref = self.titles_col.document(title_id)
        if not title_ref.get().exists:
            return False

        combo_id = self._make_combo_id(language, resolution)
        media_doc_ref = title_ref.collection("media_items").document(combo_id)
        existing = media_doc_ref.get()

        data: Dict[str, Any] = {
            "title_id": title_id,
            "language": language.strip(),
            "language_lower": language.strip().lower(),
            "resolution": resolution.strip(),
            "resolution_lower": resolution.strip().lower(),
            "file_size": file_size.strip(),
            "extra_note": extra_note.strip(),
            "updated_at": self._now(),
        }

        if not existing.exists:
            data["watch_url"] = (watch_url or "").strip()
            data["download_url"] = (download_url or "").strip()
            data["created_at"] = self._now()
            media_doc_ref.set(data)
        else:
            if watch_url is not None:
                data["watch_url"] = watch_url.strip()
            if download_url is not None:
                data["download_url"] = download_url.strip()
            media_doc_ref.update(data)

        logger.info("Updated media item %s for title %s", combo_id, title_id)
        return True

    def delete_media_url(self, title_id: str, language: str, resolution: str) -> bool:
        """Delete specific media combination."""
        combo_id = self._make_combo_id(language, resolution)
        media_ref = self.titles_col.document(title_id).collection("media_items").document(combo_id)
        if not media_ref.get().exists:
            return False
        media_ref.delete()
        return True

    def get_media_urls_for_title(self, title_id: str) -> List[Dict[str, Any]]:
        """Get all media URL combinations for a specific title."""
        media_col = self.titles_col.document(title_id).collection("media_items")
        docs = media_col.stream()
        items = []
        for doc in docs:
            d = doc.to_dict()
            d["id"] = doc.id
            items.append(d)
        return items

    def get_media_url(
        self,
        title_id: str,
        language: str,
        resolution: str
    ) -> Optional[Dict[str, Any]]:
        """Get specific media combination details."""
        combo_id = self._make_combo_id(language, resolution)
        doc = self.titles_col.document(title_id).collection("media_items").document(combo_id).get()
        if doc.exists:
            d = doc.to_dict()
            d["id"] = doc.id
            return d
        return None

    # =========================================================================
    # ADVANCED SEARCH ENGINE
    # =========================================================================

    def search_exact_title(self, title: str) -> Optional[Dict[str, Any]]:
        """Search title by exact title match (case-insensitive)."""
        clean = title.strip().lower()
        query = (
            self.titles_col
            .where(filter=FieldFilter("title_lower", "==", clean))
            .where(filter=FieldFilter("is_published", "==", True))
            .limit(1)
        )
        docs = list(query.stream())
        if docs:
            res = docs[0].to_dict()
            res["id"] = docs[0].id
            return res
        return None

    def search_titles(
        self,
        query_str: str,
        limit: int = 15,
        user_id: Optional[Union[int, str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Unified multi-strategy search:
        1. Exact Title Match
        2. Search Token Prefix / Contains (keywords, title words, aliases)
        3. Fallback partial substring scan
        Logs search query automatically if user_id is provided.
        """
        query_clean = query_str.strip().lower()
        if not query_clean:
            return []

        matched_ids = set()
        results: List[Dict[str, Any]] = []

        # 1. Exact Match Check
        exact = self.search_exact_title(query_clean)
        if exact:
            results.append(exact)
            matched_ids.add(exact["id"])

        # 2. Token / Keyword / Alias array containment
        query_words = [w for w in query_clean.split() if len(w) > 1] or [query_clean]
        for word in query_words[:3]:  # search top keywords
            q = (
                self.titles_col
                .where(filter=FieldFilter("search_tokens", "array_contains", word))
                .where(filter=FieldFilter("is_published", "==", True))
                .limit(limit)
            )
            for doc in q.stream():
                if doc.id not in matched_ids:
                    item = doc.to_dict()
                    item["id"] = doc.id
                    results.append(item)
                    matched_ids.add(doc.id)
                if len(results) >= limit:
                    break

        # 3. Substring / Prefix match fallback if few results
        if len(results) < limit:
            prefix_end = query_clean + "\uf8ff"
            q_prefix = (
                self.titles_col
                .where(filter=FieldFilter("title_lower", ">=", query_clean))
                .where(filter=FieldFilter("title_lower", "<=", prefix_end))
                .where(filter=FieldFilter("is_published", "==", True))
                .limit(limit)
            )
            for doc in q_prefix.stream():
                if doc.id not in matched_ids:
                    item = doc.to_dict()
                    item["id"] = doc.id
                    results.append(item)
                    matched_ids.add(doc.id)
                if len(results) >= limit:
                    break

        # Log search action
        if user_id is not None:
            self.log_search(
                user_id=user_id,
                keyword=query_str,
                results_count=len(results),
                top_result_id=results[0]["id"] if results else None
            )

        return results[:limit]

    def get_search_suggestions(self, query_str: str, limit: int = 6) -> List[str]:
        """Provide auto-complete search suggestions based on query."""
        results = self.search_titles(query_str, limit=limit)
        suggestions = []
        for r in results:
            t = r.get("title", "")
            if t and t not in suggestions:
                suggestions.append(t)
        return suggestions

    # =========================================================================
    # BOT SETTINGS & HELP TEXT
    # =========================================================================

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting by key."""
        doc = self.settings_col.document(key).get()
        if doc.exists:
            return doc.to_dict().get("value", default)
        return default

    def set_setting(self, key: str, value: Any, description: str = "") -> None:
        """Set or update a configuration setting."""
        self.settings_col.document(key).set({
            "key": key,
            "value": value,
            "description": description,
            "updated_at": self._now()
        })

    def get_help_text(self) -> str:
        """Retrieve dynamic bot help text."""
        default_help = (
            "👋 *Welcome to the Media Bot!*\n\n"
            "• Use the search bar or send any movie/series title.\n"
            "• Browse by categories or available languages.\n"
            "• Select preferred quality to get instant watch or download links.\n"
        )
        return str(self.get_setting("help_text", default_help))

    def set_help_text(self, text: str) -> None:
        """Update bot help text."""
        self.set_setting("help_text", text, description="Bot /help response message")

    def get_all_settings(self) -> Dict[str, Any]:
        """Fetch all stored bot settings."""
        settings = {}
        for doc in self.settings_col.stream():
            d = doc.to_dict()
            settings[d.get("key", doc.id)] = d.get("value")
        return settings

    # =========================================================================
    # SEARCH LOGS
    # =========================================================================

    def log_search(
        self,
        user_id: Union[int, str],
        keyword: str,
        results_count: int,
        top_result_id: Optional[str] = None
    ) -> str:
        """Log a user search query."""
        data = {
            "user_id": int(user_id),
            "keyword": keyword.strip(),
            "keyword_lower": keyword.strip().lower(),
            "results_count": int(results_count),
            "top_result_id": top_result_id or "",
            "timestamp": self._now(),
        }
        _, doc_ref = self.search_logs_col.add(data)
        return doc_ref.id

    def get_recent_search_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent search logs for analytics."""
        query = self.search_logs_col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(limit)
        logs = []
        for doc in query.stream():
            item = doc.to_dict()
            item["id"] = doc.id
            logs.append(item)
        return logs

    def get_top_searched_keywords(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Aggregate popular search keywords."""
        logs = self.get_recent_search_logs(limit=200)
        counts: Dict[str, int] = {}
        for l in logs:
            kw = l.get("keyword_lower", "")
            if kw:
                counts[kw] = counts.get(kw, 0) + 1

        sorted_kws = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"keyword": kw, "count": count} for kw, count in sorted_kws[:limit]]
