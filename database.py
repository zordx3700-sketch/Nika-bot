# FILE: database.py
# CHANGE: Added complete Language -> Regulation -> Link hierarchy support, Episode-by-ID lookup, persistent Add menus, and multi-button URL structure

"""
Production-Ready Firebase Firestore Database Manager for Telegram Anime & Media Bot.

Compatible with:
- Python: 3.11+
- firebase-admin: >=6.5.0

Supports:
- Users & Activity Tracking
- Categories (Add, Edit, Reorder, Enable/Disable, Delete)
- Titles (Normal / Series, Category-Scoped, Keywords, Aliases, Search Tokens)
- Seasons & Episodes for Series titles (with quick Episode-by-ID indexing)
- Hierarchical Content System:
    Title / Episode -> Languages -> Regulations -> Multi-URL Buttons
- Independent Language + Regulation + Link Relations (Hindi 2025 vs Hindi 2022 vs Bangla 2025)
- Multi-URL Buttons with custom labels (Download, Watch, Telegram, Server 2, etc.)
- Advanced Search Engine (Titles, Keywords, Aliases, Substrings, Suggestions)
- User Media Requests (Stored & forwarded to Admin)
- Bot Settings & Dynamic Help text
"""

import os
import json
import base64
import logging
import uuid
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
    """Production Firestore Database Manager."""

    def __init__(self, db_client: Optional[firestore.firestore.Client] = None):
        self.db: firestore.firestore.Client = db_client or _get_firestore_client()

        # Root Collections
        self.users_col = self.db.collection("users")
        self.categories_col = self.db.collection("categories")
        self.titles_col = self.db.collection("titles")
        self.languages_col = self.db.collection("languages")
        self.resolutions_col = self.db.collection("resolutions")
        self.settings_col = self.db.collection("settings")
        self.search_logs_col = self.db.collection("search_logs")
        self.requests_col = self.db.collection("requests")

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
        language_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new user or update existing user activity."""
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
        """Retrieve user document by ID."""
        doc = self.users_col.document(str(user_id)).get()
        if doc.exists:
            res = doc.to_dict() or {}
            res["id"] = doc.id
            return res
        return None

    def get_total_users(self) -> int:
        """Count total registered users."""
        try:
            count_query = self.users_col.count()
            results = count_query.get()
            return int(results[0][0].value)
        except Exception:
            return len(list(self.users_col.stream()))

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
        is_enabled: Optional[bool] = None,
    ) -> bool:
        """Edit category attributes."""
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
        """Delete a category."""
        doc_ref = self.categories_col.document(category_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        logger.info("Deleted category: %s", category_id)
        return True

    def set_category_enabled(self, category_id: str, is_enabled: bool) -> bool:
        """Enable or disable category."""
        return self.edit_category(category_id, is_enabled=is_enabled)

    def get_all_categories(self, only_enabled: bool = False) -> List[Dict[str, Any]]:
        """Get all categories ordered by display order."""
        query = self.categories_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))

        docs = query.order_by("order").stream()
        categories = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            categories.append(item)
        return categories

    def get_category(self, category_id: str) -> Optional[Dict[str, Any]]:
        """Get single category by ID."""
        if not category_id:
            return None
        doc = self.categories_col.document(category_id).get()
        if doc.exists:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            return item
        return None

    # =========================================================================
    # GLOBAL LANGUAGES & REGULATIONS (PRESETS/DEFAULTS)
    # =========================================================================

    def add_language(self, name: str, code: str = "", order: int = 0, is_enabled: bool = True) -> str:
        """Add a preset language."""
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
        is_enabled: Optional[bool] = None,
    ) -> bool:
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
        doc_ref = self.languages_col.document(language_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def set_language_enabled(self, language_id: str, is_enabled: bool) -> bool:
        return self.edit_language(language_id, is_enabled=is_enabled)

    def get_available_languages(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        query = self.languages_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))

        docs = query.order_by("order").stream()
        languages = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            languages.append(item)
        return languages

    def add_resolution(self, name: str, order: int = 0, is_enabled: bool = True) -> str:
        """Add a preset resolution/regulation."""
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
        is_enabled: Optional[bool] = None,
    ) -> bool:
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
        doc_ref = self.resolutions_col.document(resolution_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def set_resolution_enabled(self, resolution_id: str, is_enabled: bool) -> bool:
        return self.edit_resolution(resolution_id, is_enabled=is_enabled)

    def get_available_resolutions(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        query = self.resolutions_col
        if only_enabled:
            query = query.where(filter=FieldFilter("is_enabled", "==", True))

        docs = query.order_by("order").stream()
        resolutions = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            resolutions.append(item)
        return resolutions

    # =========================================================================
    # TITLES (NORMAL / SERIES) & CATEGORY ASSIGNMENT
    # =========================================================================

    def _build_search_tokens(self, title: str, keywords: List[str], aliases: List[str]) -> List[str]:
        """Build normalized search tokens for fast index matching."""
        tokens = set()
        t_clean = title.strip().lower()
        tokens.add(t_clean)
        for word in t_clean.split():
            if len(word) > 1:
                tokens.add(word)

        for kw in keywords:
            clean_kw = kw.strip().lower()
            if clean_kw:
                tokens.add(clean_kw)
                for w in clean_kw.split():
                    if len(w) > 1:
                        tokens.add(w)

        for al in aliases:
            clean_al = al.strip().lower()
            if clean_al:
                tokens.add(clean_al)
                for w in clean_al.split():
                    if len(w) > 1:
                        tokens.add(w)

        return list(tokens)

    def add_title(
        self,
        title: str,
        category_ids: Optional[List[str]] = None,
        content_type: str = "normal",  # "normal" or "series"
        keywords: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        poster_url: str = "",
        description: str = "",
        release_year: Optional[int] = None,
        is_published: bool = True,
    ) -> str:
        t_clean = title.strip()
        kw_list = [k.strip().lower() for k in (keywords or []) if k.strip()]
        al_list = [a.strip() for a in (aliases or []) if a.strip()]
        tokens = self._build_search_tokens(t_clean, kw_list, al_list)

        data = {
            "title": t_clean,
            "title_lower": t_clean.lower(),
            "content_type": "series" if content_type == "series" else "normal",
            "category_ids": category_ids or [],
            "keywords": kw_list,
            "aliases": al_list,
            "search_tokens": tokens,
            "poster_url": poster_url.strip(),
            "description": description.strip(),
            "release_year": release_year,
            "is_published": bool(is_published),
            "languages_map": {},  # { "Hindi": ["2025 Regulation", "2022 Regulation"], ... }
            "view_count": 0,
            "created_at": self._now(),
            "updated_at": self._now(),
        }

        _, doc_ref = self.titles_col.add(data)
        logger.info("Added title '%s' (type: %s) with ID %s", t_clean, data["content_type"], doc_ref.id)
        return doc_ref.id

    def edit_title(
        self,
        title_id: str,
        title: Optional[str] = None,
        category_ids: Optional[List[str]] = None,
        content_type: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        aliases: Optional[List[str]] = None,
        poster_url: Optional[str] = None,
        description: Optional[str] = None,
        release_year: Optional[int] = None,
        is_published: Optional[bool] = None,
    ) -> bool:
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

        if content_type is not None:
            update_data["content_type"] = "series" if content_type == "series" else "normal"

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

        update_data["search_tokens"] = self._build_search_tokens(curr_title, curr_keywords, curr_aliases)
        doc_ref.update(update_data)
        return True

    def delete_title(self, title_id: str) -> bool:
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False

        for m_doc in doc_ref.collection("media_items").stream():
            m_doc.reference.delete()

        for s_doc in doc_ref.collection("seasons").stream():
            for ep_doc in s_doc.reference.collection("episodes").stream():
                for ep_m_doc in ep_doc.reference.collection("media_items").stream():
                    ep_m_doc.reference.delete()
                ep_doc.reference.delete()
            s_doc.reference.delete()

        doc_ref.delete()
        logger.info("Deleted title %s", title_id)
        return True

    def get_title(self, title_id: str) -> Optional[Dict[str, Any]]:
        if not title_id:
            return None
        doc = self.titles_col.document(title_id).get()
        if doc.exists:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            return item
        return None

    def get_titles_by_category(
        self,
        category_id: str,
        only_published: bool = True,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        query = self.titles_col.where(filter=FieldFilter("category_ids", "array_contains", category_id))
        if only_published:
            query = query.where(filter=FieldFilter("is_published", "==", True))

        docs = query.limit(limit).stream()
        results = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            results.append(item)
        return results

    def get_all_titles(self, only_published: bool = False, limit: int = 150) -> List[Dict[str, Any]]:
        query = self.titles_col
        if only_published:
            query = query.where(filter=FieldFilter("is_published", "==", True))

        docs = query.order_by("updated_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        results = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            results.append(item)
        return results

    def assign_categories_to_title(self, title_id: str, category_ids: List[str]) -> bool:
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.update({"category_ids": category_ids, "updated_at": self._now()})
        return True

    def add_keyword(self, title_id: str, keyword: str) -> bool:
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
        kw = keyword.strip().lower()
        doc_ref = self.titles_col.document(title_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        kws = [k for k in data.get("keywords", []) if k != kw]
        return self.edit_title(title_id, keywords=kws)

    # =========================================================================
    # SEASONS & EPISODES (SERIES SYSTEM)
    # =========================================================================

    def add_season(self, title_id: str, season_number: int, season_name: str = "") -> str:
        name = season_name.strip() or f"Season {season_number}"
        data = {
            "title_id": title_id,
            "season_number": int(season_number),
            "season_name": name,
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        seasons_col = self.titles_col.document(title_id).collection("seasons")
        _, doc_ref = seasons_col.add(data)
        logger.info("Added season %s to title %s", name, title_id)
        return doc_ref.id

    def get_seasons(self, title_id: str) -> List[Dict[str, Any]]:
        seasons_col = self.titles_col.document(title_id).collection("seasons")
        docs = seasons_col.order_by("season_number").stream()
        results = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            results.append(item)
        return results

    def get_season(self, title_id: str, season_id: str) -> Optional[Dict[str, Any]]:
        doc = self.titles_col.document(title_id).collection("seasons").document(season_id).get()
        if doc.exists:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            return item
        return None

    def delete_season(self, title_id: str, season_id: str) -> bool:
        s_ref = self.titles_col.document(title_id).collection("seasons").document(season_id)
        if not s_ref.get().exists:
            return False

        for ep_doc in s_ref.collection("episodes").stream():
            for m_doc in ep_doc.reference.collection("media_items").stream():
                m_doc.reference.delete()
            ep_doc.reference.delete()

        s_ref.delete()
        return True

    def add_episode(
        self,
        title_id: str,
        season_id: str,
        episode_number: int,
        episode_title: str = "",
    ) -> str:
        ep_name = episode_title.strip() or f"Episode {episode_number}"
        data = {
            "title_id": title_id,
            "season_id": season_id,
            "episode_number": int(episode_number),
            "episode_title": ep_name,
            "languages_map": {},  # { "Hindi": ["2025 Regulation"], ... }
            "created_at": self._now(),
            "updated_at": self._now(),
        }
        ep_col = (
            self.titles_col.document(title_id)
            .collection("seasons")
            .document(season_id)
            .collection("episodes")
        )
        _, doc_ref = ep_col.add(data)
        logger.info("Added episode %s to season %s", ep_name, season_id)
        return doc_ref.id

    def get_episodes(self, title_id: str, season_id: str) -> List[Dict[str, Any]]:
        ep_col = (
            self.titles_col.document(title_id)
            .collection("seasons")
            .document(season_id)
            .collection("episodes")
        )
        docs = ep_col.order_by("episode_number").stream()
        results = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            results.append(item)
        return results

    def get_episode(self, title_id: str, season_id: str, episode_id: str) -> Optional[Dict[str, Any]]:
        doc = (
            self.titles_col.document(title_id)
            .collection("seasons")
            .document(season_id)
            .collection("episodes")
            .document(episode_id)
            .get()
        )
        if doc.exists:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            return item
        return None

    def get_episode_by_id(self, episode_id: str, title_id: Optional[str] = None, season_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Look up episode document directly or via collection group."""
        if title_id and season_id:
            return self.get_episode(title_id, season_id, episode_id)

        # Query collection group 'episodes'
        try:
            docs = self.db.collection_group("episodes").where(filter=FieldFilter("__name__", "==", episode_id)).stream()
            for doc in docs:
                item = doc.to_dict() or {}
                item["id"] = doc.id
                return item
        except Exception:
            pass

        # Fallback scan through titles/seasons
        for t_doc in self.titles_col.where(filter=FieldFilter("content_type", "==", "series")).stream():
            for s_doc in t_doc.reference.collection("seasons").stream():
                ep_doc = s_doc.reference.collection("episodes").document(episode_id).get()
                if ep_doc.exists:
                    item = ep_doc.to_dict() or {}
                    item["id"] = ep_doc.id
                    item["title_id"] = t_doc.id
                    item["season_id"] = s_doc.id
                    return item
        return None

    def delete_episode(self, title_id: str, season_id: str, episode_id: str) -> bool:
        ep_ref = (
            self.titles_col.document(title_id)
            .collection("seasons")
            .document(season_id)
            .collection("episodes")
            .document(episode_id)
        )
        if not ep_ref.get().exists:
            return False

        for m_doc in ep_ref.collection("media_items").stream():
            m_doc.reference.delete()

        ep_ref.delete()
        return True

    # =========================================================================
    # HIERARCHICAL LANGUAGE -> REGULATION -> LINK SYSTEM
    # =========================================================================

    @staticmethod
    def _make_combo_id(language: str, regulation: str) -> str:
        """Deterministic Firestore document ID for language + regulation."""
        clean_l = "".join(c if c.isalnum() else "_" for c in language.strip().lower())
        clean_r = "".join(c if c.isalnum() else "_" for c in regulation.strip().lower())
        return f"{clean_l}__{clean_r}"

    def _get_target_doc_ref(
        self,
        title_id: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ):
        """Get document reference for Title or Episode."""
        if season_id and episode_id:
            return (
                self.titles_col.document(title_id)
                .collection("seasons")
                .document(season_id)
                .collection("episodes")
                .document(episode_id)
            )
        return self.titles_col.document(title_id)

    def _get_media_ref(
        self,
        title_id: str,
        language: str,
        regulation: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ):
        combo_id = self._make_combo_id(language, regulation)
        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        return target_ref.collection("media_items").document(combo_id)

    # --- LANGUAGES IN CONTENT ---

    def get_languages_for_content(
        self,
        title_id: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        only_with_links: bool = False,
    ) -> List[str]:
        """
        Get all languages configured for this Title / Episode.
        If only_with_links=True, returns ONLY languages that have at least one regulation with links!
        """
        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        target_doc = target_ref.get()
        if not target_doc.exists:
            return []

        data = target_doc.to_dict() or {}
        lang_map = data.get("languages_map", {})

        # Also inspect media_items subcollection to catch any existing combos
        combos = list(target_ref.collection("media_items").stream())
        all_langs = set(lang_map.keys())

        for c_doc in combos:
            c_data = c_doc.to_dict() or {}
            l = c_data.get("language")
            if l:
                all_langs.add(l)

        if not only_with_links:
            return sorted(list(all_langs))

        # Filter: Only languages with actual links
        valid_langs = set()
        for c_doc in combos:
            c_data = c_doc.to_dict() or {}
            l = c_data.get("language", "")
            links = c_data.get("links", [])
            w_urls = c_data.get("watch_urls", [])
            dl_urls = c_data.get("download_urls", [])
            if l and (links or w_urls or dl_urls or c_data.get("watch_url") or c_data.get("download_url")):
                valid_langs.add(l)

        return sorted(list(valid_langs))

    def add_language_to_content(
        self,
        title_id: str,
        language: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Add a language entry to Title or Episode."""
        lang_clean = language.strip()
        if not lang_clean:
            return False

        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        doc = target_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        lang_map = dict(data.get("languages_map", {}))
        if lang_clean not in lang_map:
            lang_map[lang_clean] = []
            target_ref.update({"languages_map": lang_map, "updated_at": self._now()})

        return True

    def delete_language_from_content(
        self,
        title_id: str,
        language: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Remove language and all associated regulations/links from this Title or Episode."""
        lang_clean = language.strip()
        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        doc = target_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        lang_map = dict(data.get("languages_map", {}))
        if lang_clean in lang_map:
            del lang_map[lang_clean]
            target_ref.update({"languages_map": lang_map, "updated_at": self._now()})

        # Delete all media_items for this language
        for m_doc in target_ref.collection("media_items").stream():
            m_data = m_doc.to_dict() or {}
            if m_data.get("language", "").lower() == lang_clean.lower():
                m_doc.reference.delete()

        return True

    # --- REGULATIONS IN LANGUAGE ---

    def get_regulations_for_content(
        self,
        title_id: str,
        language: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        only_with_links: bool = False,
    ) -> List[str]:
        """
        Get all regulations configured under a specific language for Title or Episode.
        If only_with_links=True, returns ONLY regulations that have at least one valid link!
        """
        lang_clean = language.strip()
        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        doc = target_ref.get()
        if not doc.exists:
            return []

        data = doc.to_dict() or {}
        lang_map = data.get("languages_map", {})
        regs_set = set(lang_map.get(lang_clean, []))

        # Inspect media_items for this language
        combos = list(target_ref.collection("media_items").stream())
        for c_doc in combos:
            c_data = c_doc.to_dict() or {}
            if c_data.get("language", "").lower() == lang_clean.lower():
                r = c_data.get("regulation") or c_data.get("resolution")
                if r:
                    regs_set.add(r)

        if not only_with_links:
            return sorted(list(regs_set))

        # Filter: Only regulations with actual links
        valid_regs = set()
        for c_doc in combos:
            c_data = c_doc.to_dict() or {}
            if c_data.get("language", "").lower() == lang_clean.lower():
                r = c_data.get("regulation") or c_data.get("resolution", "")
                links = c_data.get("links", [])
                w_urls = c_data.get("watch_urls", [])
                dl_urls = c_data.get("download_urls", [])
                if r and (links or w_urls or dl_urls or c_data.get("watch_url") or c_data.get("download_url")):
                    valid_regs.add(r)

        return sorted(list(valid_regs))

    def add_regulation_to_content(
        self,
        title_id: str,
        language: str,
        regulation: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Add a regulation under a language for Title or Episode."""
        lang_clean = language.strip()
        reg_clean = regulation.strip()
        if not lang_clean or not reg_clean:
            return False

        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        doc = target_ref.get()
        if not doc.exists:
            return False

        data = doc.to_dict() or {}
        lang_map = dict(data.get("languages_map", {}))
        regs = list(lang_map.get(lang_clean, []))
        if reg_clean not in regs:
            regs.append(reg_clean)
            lang_map[lang_clean] = regs
            target_ref.update({"languages_map": lang_map, "updated_at": self._now()})

        # Ensure media_item document is created
        media_ref = self._get_media_ref(title_id, lang_clean, reg_clean, season_id, episode_id)
        if not media_ref.get().exists:
            media_ref.set({
                "title_id": title_id,
                "season_id": season_id or "",
                "episode_id": episode_id or "",
                "language": lang_clean,
                "regulation": reg_clean,
                "resolution": reg_clean,  # backward compat
                "links": [],
                "watch_urls": [],
                "download_urls": [],
                "created_at": self._now(),
                "updated_at": self._now(),
            })

        return True

    def delete_regulation_from_content(
        self,
        title_id: str,
        language: str,
        regulation: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Delete regulation and its links."""
        lang_clean = language.strip()
        reg_clean = regulation.strip()

        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        doc = target_ref.get()
        if doc.exists:
            data = doc.to_dict() or {}
            lang_map = dict(data.get("languages_map", {}))
            regs = list(lang_map.get(lang_clean, []))
            if reg_clean in regs:
                regs.remove(reg_clean)
                lang_map[lang_clean] = regs
                target_ref.update({"languages_map": lang_map, "updated_at": self._now()})

        media_ref = self._get_media_ref(title_id, lang_clean, reg_clean, season_id, episode_id)
        if media_ref.get().exists:
            media_ref.delete()

        return True

    # --- LINKS & BUTTONS IN REGULATION ---

    def get_links_for_content(
        self,
        title_id: str,
        language: str,
        regulation: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all links / buttons for a specific Language + Regulation.
        Returns normalized list of dicts: [ {"id": "...", "label": "...", "url": "..."}, ... ]
        """
        media_ref = self._get_media_ref(title_id, language, regulation, season_id, episode_id)
        doc = media_ref.get()
        if not doc.exists:
            return []

        data = doc.to_dict() or {}
        raw_links = data.get("links", [])
        normalized_links: List[Dict[str, Any]] = []

        for idx, item in enumerate(raw_links):
            if isinstance(item, dict):
                normalized_links.append({
                    "id": item.get("id", str(idx)),
                    "label": item.get("label", "Download"),
                    "url": item.get("url", ""),
                })
            elif isinstance(item, str):
                normalized_links.append({
                    "id": str(idx),
                    "label": "Download",
                    "url": item,
                })

        # Legacy backward compatibility check
        if not normalized_links:
            w_urls = data.get("watch_urls", [])
            dl_urls = data.get("download_urls", [])
            w_labels = data.get("watch_labels", [])
            dl_labels = data.get("download_labels", [])

            if data.get("watch_url") and data.get("watch_url") not in w_urls:
                w_urls.insert(0, data.get("watch_url"))
            if data.get("download_url") and data.get("download_url") not in dl_urls:
                dl_urls.insert(0, data.get("download_url"))

            for idx, w in enumerate(w_urls):
                if w:
                    lbl = w_labels[idx] if idx < len(w_labels) and w_labels[idx] else (f"Watch {idx+1}" if len(w_urls) > 1 else "Watch Online")
                    normalized_links.append({"id": f"w_{idx}", "label": lbl, "url": w})

            for idx, dl in enumerate(dl_urls):
                if dl:
                    lbl = dl_labels[idx] if idx < len(dl_labels) and dl_labels[idx] else (f"Download {idx+1}" if len(dl_urls) > 1 else "Download Now")
                    normalized_links.append({"id": f"dl_{idx}", "label": lbl, "url": dl})

        return [l for l in normalized_links if l.get("url")]

    def add_link_to_content(
        self,
        title_id: str,
        language: str,
        regulation: str,
        url: str,
        label: str = "Download",
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """
        Add a URL / Button to the specific Language + Regulation combination.
        Automatically registers Language and Regulation in the parent if not yet present.
        """
        clean_url = url.strip()
        if not clean_url:
            return False

        clean_lang = language.strip()
        clean_reg = regulation.strip()
        clean_label = label.strip() or "Download"

        # 1. Ensure language & regulation in parent document
        self.add_language_to_content(title_id, clean_lang, season_id, episode_id)
        self.add_regulation_to_content(title_id, clean_lang, clean_reg, season_id, episode_id)

        # 2. Add link to media_items document
        media_ref = self._get_media_ref(title_id, clean_lang, clean_reg, season_id, episode_id)
        doc = media_ref.get()

        new_link = {
            "id": str(uuid.uuid4())[:8],
            "label": clean_label,
            "url": clean_url,
            "created_at": self._now().isoformat(),
        }

        if not doc.exists:
            data = {
                "title_id": title_id,
                "season_id": season_id or "",
                "episode_id": episode_id or "",
                "language": clean_lang,
                "regulation": clean_reg,
                "resolution": clean_reg,
                "links": [new_link],
                "watch_urls": [clean_url] if "watch" in clean_label.lower() else [],
                "download_urls": [clean_url] if "watch" not in clean_label.lower() else [],
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            media_ref.set(data)
        else:
            existing = doc.to_dict() or {}
            links = list(existing.get("links", []))
            # If migrating from legacy watch_urls / download_urls
            if not links:
                for w in existing.get("watch_urls", []):
                    links.append({"id": str(uuid.uuid4())[:8], "label": "Watch Online", "url": w})
                for d in existing.get("download_urls", []):
                    links.append({"id": str(uuid.uuid4())[:8], "label": "Download", "url": d})

            links.append(new_link)
            media_ref.update({
                "links": links,
                "updated_at": self._now(),
            })

        logger.info(
            "Added link '%s' (%s) to %s (lang: %s, reg: %s)",
            clean_label, clean_url, title_id, clean_lang, clean_reg
        )
        return True

    def remove_link_from_content(
        self,
        title_id: str,
        language: str,
        regulation: str,
        link_id_or_url: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Remove a specific link from Language + Regulation combination."""
        media_ref = self._get_media_ref(title_id, language, regulation, season_id, episode_id)
        doc = media_ref.get()
        if not doc.exists:
            return False

        existing = doc.to_dict() or {}
        links = list(existing.get("links", []))
        updated_links = [
            l for l in links
            if l.get("id") != link_id_or_url and l.get("url") != link_id_or_url
        ]

        media_ref.update({
            "links": updated_links,
            "watch_urls": [l.get("url") for l in updated_links if "watch" in l.get("label", "").lower()],
            "download_urls": [l.get("url") for l in updated_links if "watch" not in l.get("label", "").lower()],
            "updated_at": self._now(),
        })
        return True

    # --- BACKWARD COMPATIBILITY COMBOS GETTERS ---

    def get_media_url_combo(
        self,
        title_id: str,
        language: str,
        resolution: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get combo dict containing both modern 'links' and legacy watch/download lists."""
        media_ref = self._get_media_ref(title_id, language, resolution, season_id, episode_id)
        doc = media_ref.get()
        if not doc.exists:
            return None

        d = doc.to_dict() or {}
        d["id"] = doc.id
        d["links"] = self.get_links_for_content(title_id, language, resolution, season_id, episode_id)
        return d

    def get_all_media_combos_for_title(
        self,
        title_id: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all media combinations for title/episode."""
        target_ref = self._get_target_doc_ref(title_id, season_id, episode_id)
        docs = target_ref.collection("media_items").stream()
        results = []
        for doc in docs:
            d = doc.to_dict() or {}
            d["id"] = doc.id
            lang = d.get("language", "")
            reg = d.get("regulation") or d.get("resolution", "")
            d["links"] = self.get_links_for_content(title_id, lang, reg, season_id, episode_id)
            results.append(d)
        return results

    # =========================================================================
    # ADVANCED SEARCH ENGINE
    # =========================================================================

    def search_titles(
        self,
        query_str: str,
        category_id: Optional[str] = None,
        limit: int = 15,
        user_id: Optional[Union[int, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Multi-strategy search across titles, search_tokens, keywords and aliases."""
        query_clean = query_str.strip().lower()
        if not query_clean:
            return []

        matched_ids = set()
        results: List[Dict[str, Any]] = []

        # 1. Search tokens
        query_words = [w for w in query_clean.split() if len(w) > 1] or [query_clean]
        for word in query_words[:3]:
            q = self.titles_col.where(filter=FieldFilter("search_tokens", "array_contains", word)).where(
                filter=FieldFilter("is_published", "==", True)
            )
            for doc in q.stream():
                if doc.id not in matched_ids:
                    item = doc.to_dict() or {}
                    item["id"] = doc.id
                    if not category_id or category_id in item.get("category_ids", []):
                        results.append(item)
                        matched_ids.add(doc.id)
                if len(results) >= limit:
                    break

        # 2. Substring fallback scan if limited results
        if len(results) < limit:
            all_titles = self.titles_col.where(filter=FieldFilter("is_published", "==", True)).stream()
            for doc in all_titles:
                if doc.id in matched_ids:
                    continue
                item = doc.to_dict() or {}
                t_low = item.get("title_lower", "")
                aliases_low = [a.lower() for a in item.get("aliases", [])]
                kws_low = [k.lower() for k in item.get("keywords", [])]

                if (
                    query_clean in t_low
                    or any(query_clean in a for a in aliases_low)
                    or any(query_clean in k for k in kws_low)
                ):
                    if not category_id or category_id in item.get("category_ids", []):
                        item["id"] = doc.id
                        results.append(item)
                        matched_ids.add(doc.id)

                if len(results) >= limit:
                    break

        # Log search query for analytics
        if user_id:
            try:
                self.search_logs_col.add({
                    "user_id": int(user_id),
                    "query": query_clean,
                    "results_count": len(results),
                    "created_at": self._now(),
                })
            except Exception:
                pass

        return results

    # =========================================================================
    # USER REQUESTS SYSTEM
    # =========================================================================

    def add_user_request(
        self,
        user_id: Union[int, str],
        username: str,
        request_text: str,
    ) -> str:
        """Log user anime / media request in Firestore."""
        data = {
            "user_id": int(user_id),
            "username": username or "",
            "request_text": request_text.strip(),
            "status": "pending",
            "created_at": self._now(),
        }
        _, doc_ref = self.requests_col.add(data)
        logger.info("Saved user request from %s: %s", user_id, request_text)
        return doc_ref.id

    def get_recent_requests(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch latest user requests for Admin view."""
        docs = (
            self.requests_col.order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        requests = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            requests.append(item)
        return requests

    # =========================================================================
    # SETTINGS & HELP
    # =========================================================================

    def get_help_text(self) -> str:
        """Fetch custom help text or return default."""
        doc = self.settings_col.document("help_text").get()
        if doc.exists:
            return (doc.to_dict() or {}).get("text", self._default_help())
        return self._default_help()

    def set_help_text(self, text: str) -> bool:
        """Update bot help text."""
        self.settings_col.document("help_text").set({
            "text": text.strip(),
            "updated_at": self._now(),
        })
        return True

    @staticmethod
    def _default_help() -> str:
        return (
            "📖 *Anime & Media Bot Help Guide*\n\n"
            "• **Browse by Category:** Tap **📂 Categories** to browse categories and find your favorite titles.\n"
            "• **Normal Movies/Titles:** Category ➔ Title ➔ Language ➔ Regulation ➔ Direct Links.\n"
            "• **Series & Anime:** Category ➔ Title ➔ Season ➔ Episode ➔ Language ➔ Regulation ➔ Direct Links.\n"
            "• **Instant Search:** Send any movie/anime title name in chat anytime to search.\n"
            "• **Request Media:** Tap **📩 Request** to request any missing anime or movie from admins!"
            )
