import json
import firebase_admin
from firebase_admin import credentials, firestore
from config import FIREBASE_CREDS_RAW

try:
    if FIREBASE_CREDS_RAW and FIREBASE_CREDS_RAW.startswith("{"):
        creds_dict = json.loads(FIREBASE_CREDS_RAW)
        cred = credentials.Certificate(creds_dict)
    else:
        cred = credentials.Certificate(FIREBASE_CREDS_RAW)
        
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Error initializing Firebase: {e}")
    db = None

class DatabaseManager:
    @staticmethod
    def register_user(user_id: int):
        if not db: return
        doc_ref = db.collection('users').document(str(user_id))
        if not doc_ref.get().exists:
            doc_ref.set({'telegram_id': user_id, 'created_at': firestore.SERVER_TIMESTAMP})

    @staticmethod
    def get_total_users():
        if not db: return 0
        return sum(1 for _ in db.collection('users').stream())

    # --- Anime Management ---
    @staticmethod
    def add_anime_data(anime_key, data):
        if not db: return
        db.collection('animes').document(anime_key.lower().strip()).set(data)

    @staticmethod
    def save_episode_mapping(anime_key, season, ep_num, lang, msg_id):
        if not db: return
        doc_id = f"{anime_key.lower().strip()}_s{season}_ep{ep_num}_{lang}"
        db.collection('episodes').document(doc_id).set({
            'anime_key': anime_key.lower().strip(),
            'season': str(season),
            'ep_num': int(ep_num),
            'lang': lang,
            'msg_id': int(msg_id)
        })

    @staticmethod
    def get_episode_msg_id(anime_key, season, ep_num, lang):
        if not db: return None
        doc_id = f"{anime_key.lower().strip()}_s{season}_ep{ep_num}_{lang}"
        doc = db.collection('episodes').document(doc_id).get()
        return doc.to_dict().get('msg_id') if doc.exists else None

    # --- Deletion System ---
    @staticmethod
    def delete_entire_anime(anime_key):
        if not db: return
        key = anime_key.lower().strip()
        db.collection('animes').document(key).delete()
        eps = db.collection('episodes').where('anime_key', '==', key).stream()
        for ep in eps:
            ep.reference.delete()

    @staticmethod
    def delete_language_data(anime_key, lang):
        if not db: return
        key = anime_key.lower().strip()
        # Remove lang from anime doc
        doc_ref = db.collection('animes').document(key)
        doc = doc_ref.get()
        if doc.exists:
            langs = doc.to_dict().get('languages', [])
            if lang in langs:
                langs.remove(lang)
                doc_ref.update({'languages': langs})
        # Delete episodes
        eps = db.collection('episodes').where('anime_key', '==', key).where('lang', '==', lang).stream()
        for ep in eps:
            ep.reference.delete()

    @staticmethod
    def delete_single_episode(anime_key, season, ep_num, lang):
        if not db: return
        doc_id = f"{anime_key.lower().strip()}_s{season}_ep{ep_num}_{lang}"
        db.collection('episodes').document(doc_id).delete()

    # --- Utility ---
    @staticmethod
    def search_anime(query):
        if not db: return None, []
        q = query.lower().strip()
        doc = db.collection('animes').document(q).get()
        if doc.exists:
            data = doc.to_dict()
            data['key'] = doc.id
            return data, []
            
        animes = db.collection('animes').stream()
        all_keys = []
        for d in animes:
            data = d.to_dict()
            data['key'] = d.id
            all_keys.append(d.id)
            if q in d.id or q in data['name'].lower():
                return data, []
        suggestions = [k for k in all_keys if q in k or k in q][:5]
        return None, suggestions

    @staticmethod
    def get_all_animes():
        if not db: return []
        return [doc.to_dict() | {'key': doc.id} for doc in db.collection('animes').stream()]

    @staticmethod
    def set_help_text(text):
        if not db: return
        db.collection('config').document('help').set({'text': text})

    @staticmethod
    def get_help_text():
        if not db: return "Contact Admin for help."
        doc = db.collection('config').document('help').get()
        return doc.to_dict().get('text', "Contact Admin for help.") if doc.exists else "Contact Admin for help."
