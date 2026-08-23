from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Optional

import firebase_admin
from firebase_admin import credentials, firestore

from config import FIREBASE_CREDENTIALS_B64


class DatabaseManager:
    _db = None

    @classmethod
    def init(cls):
        if cls._db is not None:
            return

        if not FIREBASE_CREDENTIALS_B64:
            raise RuntimeError(
                "FIREBASE_CREDENTIALS_B64 is not configured."
            )

        try:
            decoded = base64.b64decode(
                FIREBASE_CREDENTIALS_B64
            ).decode("utf-8")

            service_account = json.loads(decoded)

            if not firebase_admin._apps:
                cred = credentials.Certificate(service_account)
                firebase_admin.initialize_app(cred)

            cls._db = firestore.client()

        except Exception as e:
            raise RuntimeError(
                f"Firebase initialization failed: {e}"
            )

    @classmethod
    def now(cls):
        return datetime.now(timezone.utc)

    # -------------------------------------------------
    # USERS
    # -------------------------------------------------

    @classmethod
    def register_user(cls, user):
        cls.init()

        ref = cls._db.collection("users").document(
            str(user.id)
        )

        existing = ref.get()

        if existing.exists:
            ref.update({
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "updated_at": cls.now(),
            })
        else:
            ref.set({
                "telegram_id": user.id,
                "username": user.username or "",
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "created_at": cls.now(),
                "updated_at": cls.now(),
                "total_searches": 0,
                "total_episode_opens": 0,
            })

    @classmethod
    def get_user(cls, user_id: int):
        cls.init()

        snap = cls._db.collection("users").document(
            str(user_id)
        ).get()

        if not snap.exists:
            return None

        return snap.to_dict()

    @classmethod
    def get_total_users(cls):
        cls.init()

        return len(
            list(cls._db.collection("users").stream())
        )

    # -------------------------------------------------
    # SEARCH HISTORY
    # -------------------------------------------------

    @classmethod
    def add_search_history(
        cls,
        user_id: int,
        keyword: str,
        anime_name: Optional[str],
    ):
        cls.init()

        cls._db.collection("search_history").add({
            "user_id": user_id,
            "keyword": keyword,
            "anime_name": anime_name or "",
            "created_at": cls.now(),
        })

        user_ref = cls._db.collection("users").document(
            str(user_id)
        )

        user_ref.set({
            "total_searches": firestore.Increment(1)
        }, merge=True)

    @classmethod
    def get_search_history(
        cls,
        user_id: int,
        limit: int = 20,
    ):
        cls.init()

        docs = (
            cls._db.collection("search_history")
            .where("user_id", "==", user_id)
            .stream()
        )

        data = [d.to_dict() for d in docs]

        data.sort(
            key=lambda x: x.get("created_at", datetime.min),
            reverse=True
        )

        return data[:limit]

    # -------------------------------------------------
    # EPISODE HISTORY
    # -------------------------------------------------

    @classmethod
    def add_episode_history(
        cls,
        user_id: int,
        anime_name: str,
        season: int,
        episode: int,
        quality: str,
        language: str,
    ):
        cls.init()

        cls._db.collection("episode_history").add({
            "user_id": user_id,
            "anime_name": anime_name,
            "season": season,
            "episode": episode,
            "quality": quality,
            "language": language,
            "created_at": cls.now(),
        })

        cls._db.collection("users").document(
            str(user_id)
        ).set({
            "total_episode_opens": firestore.Increment(1)
        }, merge=True)

    @classmethod
    def get_episode_history(
        cls,
        user_id: int,
        limit: int = 30,
    ):
        cls.init()

        docs = (
            cls._db.collection("episode_history")
            .where("user_id", "==", user_id)
            .stream()
        )

        data = [d.to_dict() for d in docs]

        data.sort(
            key=lambda x: x.get("created_at", datetime.min),
            reverse=True
        )

        return data[:limit]

    # -------------------------------------------------
    # ANIME
    # -------------------------------------------------

    @staticmethod
    def normalize(text: str):
        return " ".join(
            text.lower().strip().split()
        )

    @classmethod
    def add_anime(
        cls,
        name: str,
        rating: float,
        poster_message_id: int,
        season_count: int,
        episodes_per_season: list[int],
        keywords: list[str],
    ):
        cls.init()

        anime_id = cls.normalize(name).replace(" ", "_")

        ref = cls._db.collection("animes").document(
            anime_id
        )

        if ref.get().exists:
            raise ValueError(
                "Anime already exists."
            )

        ref.set({
            "name": name.strip(),
            "normalized_name": cls.normalize(name),
            "rating": rating,
            "poster_message_id": poster_message_id,
            "season_count": season_count,
            "episodes_per_season": episodes_per_season,
            "keywords": [
                cls.normalize(k)
                for k in keywords
                if k.strip()
            ],
            "created_at": cls.now(),
            "updated_at": cls.now(),
        })

        return anime_id

    @classmethod
    def get_anime(cls, anime_id: str):
        cls.init()

        snap = cls._db.collection("animes").document(
            anime_id
        ).get()

        if not snap.exists:
            return None

        data = snap.to_dict()
        data["id"] = snap.id
        return data

    @classmethod
    def get_all_animes(cls):
        cls.init()

        docs = cls._db.collection("animes").stream()

        result = []

        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            result.append(data)

        result.sort(
            key=lambda x: x.get("name", "").lower()
        )

        return result

    @classmethod
    def delete_anime(cls, anime_id: str):
        cls.init()

        cls._db.collection("animes").document(
            anime_id
        ).delete()

        mappings = (
            cls._db.collection("episode_mappings")
            .where("anime_id", "==", anime_id)
            .stream()
        )

        for doc in mappings:
            doc.reference.delete()

    # -------------------------------------------------
    # KEYWORDS
    # -------------------------------------------------

    @classmethod
    def add_keyword(
        cls,
        anime_id: str,
        keyword: str,
    ):
        cls.init()

        ref = cls._db.collection("animes").document(
            anime_id
        )

        snap = ref.get()

        if not snap.exists:
            return False

        data = snap.to_dict()

        keywords = data.get("keywords", [])

        keyword = cls.normalize(keyword)

        if keyword not in keywords:
            keywords.append(keyword)

        ref.update({
            "keywords": keywords,
            "updated_at": cls.now(),
        })

        return True

    @classmethod
    def remove_keyword(
        cls,
        anime_id: str,
        keyword: str,
    ):
        cls.init()

        ref = cls._db.collection("animes").document(
            anime_id
        )

        snap = ref.get()

        if not snap.exists:
            return False

        data = snap.to_dict()

        keywords = data.get("keywords", [])

        keyword = cls.normalize(keyword)

        keywords = [
            k for k in keywords
            if k != keyword
        ]

        ref.update({
            "keywords": keywords,
            "updated_at": cls.now(),
        })

        return True

    # -------------------------------------------------
    # SEARCH
    # -------------------------------------------------

    @classmethod
    def search_anime(cls, query: str):
        cls.init()

        q = cls.normalize(query)

        animes = cls.get_all_animes()

        exact = None

        for anime in animes:
            if anime.get("normalized_name") == q:
                exact = anime
                break

        if exact:
            return exact, []

        for anime in animes:
            if q in anime.get("keywords", []):
                return anime, []

        for anime in animes:
            if q in anime.get(
                "normalized_name", ""
            ):
                return anime, []

        suggestions = []

        for anime in animes:
            name = anime.get(
                "normalized_name", ""
            )

            keywords = anime.get(
                "keywords", []
            )

            if (
                q in name
                or any(q in k for k in keywords)
                or any(
                    word in name
                    for word in q.split()
                    if len(word) >= 3
                )
            ):
                suggestions.append(
                    anime.get("name", "")
                )

        return None, suggestions[:8]

    # -------------------------------------------------
    # EPISODE MAPPINGS
    # -------------------------------------------------

    @classmethod
    def save_episode_mapping(
        cls,
        anime_id: str,
        season: int,
        episode: int,
        quality: str,
        language: str,
        channel_id: int,
        message_id: int,
    ):
        cls.init()

        mapping_id = (
            f"{anime_id}_"
            f"s{season}_"
            f"e{episode}_"
            f"{quality}_"
            f"{language.lower()}"
        )

        ref = cls._db.collection(
            "episode_mappings"
        ).document(mapping_id)

        ref.set({
            "anime_id": anime_id,
            "season": season,
            "episode": episode,
            "quality": quality,
            "language": language,
            "channel_id": channel_id,
            "message_id": message_id,
            "updated_at": cls.now(),
        })

    @classmethod
    def get_episode_mapping(
        cls,
        anime_id: str,
        season: int,
        episode: int,
        quality: str,
        language: str,
    ):
        cls.init()

        mapping_id = (
            f"{anime_id}_"
            f"s{season}_"
            f"e{episode}_"
            f"{quality}_"
            f"{language.lower()}"
        )

        snap = cls._db.collection(
            "episode_mappings"
        ).document(mapping_id).get()

        if not snap.exists:
            return None

        return snap.to_dict()

    @classmethod
    def get_available_qualities(
        cls,
        anime_id: str,
        season: int,
    ):
        cls.init()

        docs = (
            cls._db.collection("episode_mappings")
            .where("anime_id", "==", anime_id)
            .where("season", "==", season)
            .stream()
        )

        qualities = set()

        for doc in docs:
            data = doc.to_dict()
            qualities.add(data.get("quality"))

        return sorted(
            qualities,
            key=lambda q: ["480p", "720p", "1080p"].index(q)
            if q in ["480p", "720p", "1080p"]
            else 99
        )

    @classmethod
    def get_available_languages(
        cls,
        anime_id: str,
        season: int,
        quality: str,
    ):
        cls.init()

        docs = (
            cls._db.collection("episode_mappings")
            .where("anime_id", "==", anime_id)
            .where("season", "==", season)
            .where("quality", "==", quality)
            .stream()
        )

        languages = set()

        for doc in docs:
            data = doc.to_dict()
            languages.add(data.get("language"))

        return sorted(languages)

    @classmethod
    def get_episode_count(
        cls,
        anime_id: str,
        season: int,
        quality: str,
        language: str,
    ):
        cls.init()

        docs = (
            cls._db.collection("episode_mappings")
            .where("anime_id", "==", anime_id)
            .where("season", "==", season)
            .where("quality", "==", quality)
            .where("language", "==", language)
            .stream()
        )

        return len(list(docs))

    # -------------------------------------------------
    # HELP
    # -------------------------------------------------

    @classmethod
    def get_help(cls):
        cls.init()

        snap = cls._db.collection(
            "settings"
        ).document("help").get()

        if not snap.exists:
            return (
                "Use Search Anime to find your favorite Anime."
            )

        return snap.to_dict().get(
            "text",
            "Help information is unavailable."
        )

    @classmethod
    def set_help(cls, text: str):
        cls.init()

        cls._db.collection(
            "settings"
        ).document("help").set({
            "text": text,
            "updated_at": cls.now(),
        })
