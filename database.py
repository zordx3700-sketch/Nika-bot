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
    def register_user(user_id: int, username: str, first_name: str):
        if not db: return
        doc_ref = db.collection('users').document(str(user_id))
        if not doc_ref.get().exists:
            doc_ref.set({
                'telegram_id': user_id,
                'username': username or "",
                'first_name': first_name or "",
                'created_at': firestore.SERVER_TIMESTAMP
            })

    @staticmethod
    def get_total_users():
        if not db: return 0
        docs = db.collection('users').stream()
        return sum(1 for _ in docs)

    @staticmethod
    def add_anime(anime_id, name, seasons, total_eps, languages, rating, poster_url, keywords):
        if not db: return
        db.collection('animes').document(anime_id).set({
            'name': name,
            'seasons': int(seasons),
            'total_episodes': int(total_eps),
            'languages': languages, # e.g. ["Hindi", "English"]
            'rating': float(rating),
            'poster_url': poster_url,
            'keywords': [k.strip().lower() for k in keywords.split(',')]
        })

    @staticmethod
    def delete_anime(anime_id):
        if not db: return
        db.collection('animes').document(anime_id).delete()

    @staticmethod
    def search_anime(query):
        if not db: return None, []
        q = query.lower().strip()
        animes = db.collection('animes').stream()
        all_keywords = set()
        
        for doc in animes:
            data = doc.to_dict()
            data['id'] = doc.id
            k_list = data.get('keywords', [])
            all_keywords.update(k_list)
            if any(q in k for k in k_list) or q in data['name'].lower():
                return data, []
                
        suggestions = [k for k in all_keywords if q in k or k in q][:5]
        return None, suggestions
