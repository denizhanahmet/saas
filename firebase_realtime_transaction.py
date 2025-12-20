import os
import requests
from dotenv import load_dotenv
import time

load_dotenv()
FIREBASE_DB_URL = os.getenv('FIREBASE_DB_URL')

# Transaction benzeri atomic update fonksiyonu (REST API ile optimistic lock)
def atomic_update(path, update_fn, max_retries=5):
    url = f"{FIREBASE_DB_URL}{path}.json"
    for attempt in range(max_retries):
        # 1. Mevcut veriyi çek
        resp = requests.get(url)
        if resp.status_code != 200:
            raise Exception(f"Firebase GET error: {resp.text}")
        current = resp.json()
        # 2. Yeni veri hesapla
        new_data = update_fn(current)
        # 3. ETag ile koşullu güncelleme
        etag = resp.headers.get('ETag')
        headers = {'if-match': etag} if etag else {}
        put_resp = requests.put(url, json=new_data, headers=headers)
        if put_resp.status_code == 200:
            return put_resp.json()
        elif put_resp.status_code == 412:
            # Eşzamanlı değişiklik oldu, tekrar dene
            time.sleep(0.1)
            continue
        else:
            raise Exception(f"Firebase PUT error: {put_resp.text}")
    raise Exception("Atomic update failed after retries")
