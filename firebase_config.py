import os
import firebase_admin
from firebase_admin import credentials, firestore

FIREBASE_CREDENTIALS = os.getenv('FIREBASE_CREDENTIALS', 'firebase_key.json')

cred = credentials.Certificate(FIREBASE_CREDENTIALS)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()
