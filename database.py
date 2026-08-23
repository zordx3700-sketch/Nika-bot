# FILE: database.py
# CHANGE: Added content_type (normal/series), Seasons, Episodes, Multi-URL list support, Requests storage, and enhanced search engine

"""
Production-Ready Firebase Firestore Database Manager for Telegram Anime & Media Bot.

Compatible with:
- Python: 3.11+
- firebase-admin: >=6.5.0

Supports:
- Users & Activity Tracking
- Categories (Add, Edit, Reorder, Enable/Disable, Delete)
- Titles (Normal / Series, Category-Scoped, Keywords, Aliases, Search Tokens)
- Seasons & Episodes for Series titles
- Languages & Resolutions (Admin managed)
- Multiple Watch URLs and Multiple Download URLs per combination
- Advanced Search Engine (Titles, Keywords, Aliases, Substrings, Suggestions)
- User Media Requests (Stored & forwarded to Admin)
- Bot Settings & Dynamic Help text
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
    # LANGUAGES
    # =========================================================================

    def add_language(self, name: str, code: str = "", order: int = 0, is_enabled: bool = True) -> str:
        """Add a supported audio/subtitle language."""
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
        """Toggle language enabled state."""
        return self.edit_language(language_id, is_enabled=is_enabled)

    def get_available_languages(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        """Get available languages."""
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

    # =========================================================================
    # RESOLUTIONS
    # =========================================================================

    def add_resolution(self, name: str, order: int = 0, is_enabled: bool = True) -> str:
        """Add a video quality option (e.g., 480p, 720p, 1080p, 4K)."""
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
        """Edit resolution."""
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
        """Toggle resolution enabled state."""
        return self.edit_resolution(resolution_id, is_enabled=is_enabled)

    def get_available_resolutions(self, only_enabled: bool = True) -> List[Dict[str, Any]]:
        """Get available resolutions."""
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
        """
        Add a new media title scoped to category_ids.
        content_type: 'normal' (standalone movie/anime) or 'series' (seasons + episodes).
        """
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
        """Edit title and refresh search tokens."""
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
        """Delete title, all seasons, episodes, and media items."""
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False

        # Delete normal media items subcollection
        for m_doc in doc_ref.collection("media_items").stream():
            m_doc.reference.delete()

        # Delete seasons and nested episodes
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
        """Get single title by ID."""
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
        """Fetch titles scoped specifically to category_id."""
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
        """Get all titles ordered by updated_at."""
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
        """Assign list of categories to title."""
        doc_ref = self.titles_col.document(title_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.update({"category_ids": category_ids, "updated_at": self._now()})
        return True

    # =========================================================================
    # KEYWORDS MANAGEMENT
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

    # =========================================================================
    # SEASONS & EPISODES (SERIES SYSTEM)
    # =========================================================================

    def add_season(self, title_id: str, season_number: int, season_name: str = "") -> str:
        """Add a season to a series title."""
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
        """Get all seasons for a title ordered by season_number."""
        seasons_col = self.titles_col.document(title_id).collection("seasons")
        docs = seasons_col.order_by("season_number").stream()
        results = []
        for doc in docs:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            results.append(item)
        return results

    def get_season(self, title_id: str, season_id: str) -> Optional[Dict[str, Any]]:
        """Get a single season by ID."""
        doc = self.titles_col.document(title_id).collection("seasons").document(season_id).get()
        if doc.exists:
            item = doc.to_dict() or {}
            item["id"] = doc.id
            return item
        return None

    def delete_season(self, title_id: str, season_id: str) -> bool:
        """Delete a season and all its episodes."""
        s_ref = self.titles_col.document(title_id).collection("seasons").document(season_id)
        if not s_ref.get().exists:
            return False

        # Delete all episodes
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
        """Add an episode to a season."""
        ep_name = episode_title.strip() or f"Episode {episode_number}"
        data = {
            "title_id": title_id,
            "season_id": season_id,
            "episode_number": int(episode_number),
            "episode_title": ep_name,
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
        """Get all episodes for a season ordered by episode_number."""
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
        """Get a single episode by ID."""
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

    def delete_episode(self, title_id: str, season_id: str, episode_id: str) -> bool:
        """Delete an episode."""
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
    # MULTI-URL MEDIA COMBINATIONS (NORMAL & SERIES)
    # =========================================================================

    @staticmethod
    def _make_combo_id(language: str, resolution: str) -> str:
        """Generate a deterministic ID for language + resolution."""
        clean_l = "".join(c if c.isalnum() else "_" for c in language.strip().lower())
        clean_r = "".join(c if c.isalnum() else "_" for c in resolution.strip().lower())
        return f"{clean_l}__{clean_r}"

    def _get_media_ref(
        self,
        title_id: str,
        language: str,
        resolution: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ):
        """Helper to get reference to the media combination document."""
        combo_id = self._make_combo_id(language, resolution)
        if season_id and episode_id:
            return (
                self.titles_col.document(title_id)
                .collection("seasons")
                .document(season_id)
                .collection("episodes")
                .document(episode_id)
                .collection("media_items")
                .document(combo_id)
            )
        return self.titles_col.document(title_id).collection("media_items").document(combo_id)

    def add_media_url_link(
        self,
        title_id: str,
        language: str,
        resolution: str,
        url: str,
        url_type: str = "watch",  # 'watch' or 'download'
        label: str = "",
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """
        Add a URL to the combination list without overwriting existing links.
        url_type: 'watch' or 'download'.
        """
        if not url or not url.strip():
            return False

        doc_ref = self._get_media_ref(title_id, language, resolution, season_id, episode_id)
        doc = doc_ref.get()

        clean_url = url.strip()
        custom_label = label.strip()

        if not doc.exists:
            watch_urls = [clean_url] if url_type == "watch" else []
            download_urls = [clean_url] if url_type == "download" else []
            watch_labels = [custom_label] if url_type == "watch" else []
            download_labels = [custom_label] if url_type == "download" else []

            data = {
                "title_id": title_id,
                "season_id": season_id or "",
                "episode_id": episode_id or "",
                "language": language.strip(),
                "resolution": resolution.strip(),
                "watch_urls": watch_urls,
                "download_urls": download_urls,
                "watch_labels": watch_labels,
                "download_labels": download_labels,
                # Legacy compatibility fields
                "watch_url": clean_url if url_type == "watch" else "",
                "download_url": clean_url if url_type == "download" else "",
                "created_at": self._now(),
                "updated_at": self._now(),
            }
            doc_ref.set(data)
        else:
            existing = doc.to_dict() or {}
            watch_urls = list(existing.get("watch_urls", []))
            download_urls = list(existing.get("download_urls", []))
            watch_labels = list(existing.get("watch_labels", []))
            download_labels = list(existing.get("download_labels", []))

            # Include legacy single URL if not in list
            if existing.get("watch_url") and existing.get("watch_url") not in watch_urls:
                watch_urls.insert(0, existing.get("watch_url"))
            if existing.get("download_url") and existing.get("download_url") not in download_urls:
                download_urls.insert(0, existing.get("download_url"))

            if url_type == "watch":
                if clean_url not in watch_urls:
                    watch_urls.append(clean_url)
                    watch_labels.append(custom_label)
            elif url_type == "download":
                if clean_url not in download_urls:
                    download_urls.append(clean_url)
                    download_labels.append(custom_label)

            doc_ref.update({
                "watch_urls": watch_urls,
                "download_urls": download_urls,
                "watch_labels": watch_labels,
                "download_labels": download_labels,
                "watch_url": watch_urls[0] if watch_urls else "",
                "download_url": download_urls[0] if download_urls else "",
                "updated_at": self._now(),
            })

        logger.info(
            "Added %s URL to title %s (lang: %s, res: %s, ep: %s)",
            url_type,
            title_id,
            language,
            resolution,
            episode_id,
        )
        return True

    def remove_media_url_link(
        self,
        title_id: str,
        language: str,
        resolution: str,
        url: str,
        url_type: str = "watch",
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Remove a specific URL from the combination list."""
        doc_ref = self._get_media_ref(title_id, language, resolution, season_id, episode_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False

        existing = doc.to_dict() or {}
        watch_urls = list(existing.get("watch_urls", []))
        download_urls = list(existing.get("download_urls", []))

        clean_url = url.strip()
        if url_type == "watch" and clean_url in watch_urls:
            watch_urls.remove(clean_url)
        elif url_type == "download" and clean_url in download_urls:
            download_urls.remove(clean_url)

        doc_ref.update({
            "watch_urls": watch_urls,
            "download_urls": download_urls,
            "watch_url": watch_urls[0] if watch_urls else "",
            "download_url": download_urls[0] if download_urls else "",
            "updated_at": self._now(),
        })
        return True

    def delete_media_combo(
        self,
        title_id: str,
        language: str,
        resolution: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> bool:
        """Delete an entire combination document."""
        doc_ref = self._get_media_ref(title_id, language, resolution, season_id, episode_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def get_media_url_combo(
        self,
        title_id: str,
        language: str,
        resolution: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the combination document with full lists of watch/download URLs."""
        doc_ref = self._get_media_ref(title_id, language, resolution, season_id, episode_id)
        doc = doc_ref.get()
        if not doc.exists:
            return None

        d = doc.to_dict() or {}
        d["id"] = doc.id

        # Normalize URL lists
        w_list = list(d.get("watch_urls", []))
        if d.get("watch_url") and d.get("watch_url") not in w_list:
            w_list.insert(0, d.get("watch_url"))
        d["watch_urls"] = [u for u in w_list if u]

        dl_list = list(d.get("download_urls", []))
        if d.get("download_url") and d.get("download_url") not in dl_list:
            dl_list.insert(0, d.get("download_url"))
        d["download_urls"] = [u for u in dl_list if u]

        return d

    def get_all_media_combos_for_title(
        self,
        title_id: str,
        season_id: Optional[str] = None,
        episode_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve all media URL combinations for a normal title or a specific episode."""
        if season_id and episode_id:
            col = (
                self.titles_col.document(title_id)
                .collection("seasons")
                .document(season_id)
                .collection("episodes")
                .document(episode_id)
                .collection("media_items")
            )
        else:
            col = self.titles_col.document(title_id).collection("media_items")

        docs = col.stream()
        results = []
        for doc in docs:
            d = doc.to_dict() or {}
            d["id"] = doc.id
            w_list = list(d.get("watch_urls", []))
            if d.get("watch_url") and d.get("watch_url") not in w_list:
                w_list.insert(0, d.get("watch_url"))
            d["watch_urls"] = [u for u in w_list if u]

            dl_list = list(d.get("download_urls", []))
            if d.get("download_url") and d.get("download_url") not in dl_list:
                dl_list.insert(0, d.get("download_url"))
            d["download_urls"] = [u for u in dl_list if u]

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
        """
        Unified multi-strategy case-insensitive search:
        - Exact title matching
        - Keyword array containment
        - Alias matching
        - Partial substring scan across all titles in scope
        """
        query_clean = query_str.strip().lower()
        if not query_clean:
            return []

        matched_ids = set()
        results: List[Dict[str, Any]] = []

        # 1. Direct search by search_tokens
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

        # 2. Comprehensive in-memory substring match across titles if limit not reached
        if len(results) < limit:
            all_published = self.get_all_titles(only_published=True, limit=200)
            for t in all_published:
                if t["id"] in matched_ids:
                    continue
                if category_id and category_id not in t.get("category_ids", []):
                    continue

                t_title = t.get("title_lower", "")
                t_kws = t.get("keywords", [])
                t_aliases = [a.lower() for a in t.get("aliases", [])]

                if (
                    query_clean in t_title
                    or any(query_clean in kw for kw in t_kws)
                    or any(query_clean in al for al in t_aliases)
                    or any(word in t_title for word in query_words)
                ):
                    results.append(t)
                    matched_ids.add(t["id"])

                if len(results) >= limit:
                    break

        # Log search action
        if user_id is not None:
            self.log_search(
                user_id=user_id,
                keyword=query_str,
                results_count=len(results),
                top_result_id=results[0]["id"] if results else None,
            )

        return results[:limit]

    # =========================================================================
    # USER MEDIA REQUESTS
    # =========================================================================

    def save_user_request(
        self,
        user_id: int,
        first_name: str,
        username: str,
        request_text: str,
    ) -> str:
        """Save user content request in Firestore."""
        data = {
            "user_id": int(user_id),
            "first_name": first_name.strip(),
            "username": username.strip(),
            "request_text": request_text.strip(),
            "status": "pending",
            "created_at": self._now(),
        }
        _, doc_ref = self.requests_col.add(data)
        logger.info("Saved user request from %s: %s", user_id, request_text)
        return doc_ref.id

    def get_recent_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent user media requests."""
        docs = self.requests_col.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit).stream()
        results = []
        for doc in docs:
            d = doc.to_dict() or {}
            d["id"] = doc.id
            results.append(d)
        return results

    # =========================================================================
    # SETTINGS & HELP TEXT
    # =========================================================================

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting by key."""
        doc = self.settings_col.document(key).get()
        if doc.exists:
            return (doc.to_dict() or {}).get("value", default)
        return default

    def set_setting(self, key: str, value: Any, description: str = "") -> None:
        """Set or update a configuration setting."""
        self.settings_col.document(key).set({
            "key": key,
            "value": value,
            "description": description,
            "updated_at": self._now(),
        })

    def get_help_text(self) -> str:
        """Retrieve dynamic bot help text."""
        default_help = (
            "👋 *Welcome to Anime & Media Bot Help!*\n\n"
            "• Use the search bar or send any movie/series title.\n"
            "• Browse by categories or available languages.\n"
            "• Select preferred quality to get instant watch or download links.\n"
            "• Use **📩 Request** to ask for any missing anime or movie!"
        )
        return str(self.get_setting("help_text", default_help))

    def set_help_text(self, text: str) -> None:
        """Update bot help text."""
        self.set_setting("help_text", text, description="Bot /help response message")

    # =========================================================================
    # SEARCH LOGS & STATS
    # =========================================================================

    def log_search(
        self,
        user_id: Union[int, str],
        keyword: str,
        results_count: int,
        top_result_id: Optional[str] = None,
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

    def get_top_searched_keywords(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Aggregate popular search queries."""
        logs_query = self.search_logs_col.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(200)
        counts: Dict[str, int] = {}
        for doc in logs_query.stream():
            l = doc.to_dict() or {}
            kw = l.get("keyword_lower", "")
            if kw:
                counts[kw] = counts.get(kw, 0) + 1

        sorted_kws = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"keyword": kw, "count": count} for kw, count in sorted_kws[:limit]]
