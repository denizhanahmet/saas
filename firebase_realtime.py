import os
import requests
from dotenv import load_dotenv

load_dotenv()
FIREBASE_DB_URL = os.getenv('FIREBASE_DB_URL')

# Temel CRUD fonksiyonları

def add_data(path, data):
    url = f"{FIREBASE_DB_URL}{path}.json"
    response = requests.post(url, json=data)
    return response.json()

def set_data(path, data):
    url = f"{FIREBASE_DB_URL}{path}.json"
    response = requests.put(url, json=data)
    return response.json()

def get_data(path):
    url = f"{FIREBASE_DB_URL}{path}.json"
    response = requests.get(url)
    return response.json()

def update_data(path, data):
    url = f"{FIREBASE_DB_URL}{path}.json"
    response = requests.patch(url, json=data)
    return response.json()

def delete_data(path):
    url = f"{FIREBASE_DB_URL}{path}.json"
    response = requests.delete(url)
    return response.json()

# Örnek kullanım:
# add_data('users', {'username': 'ali', 'email': 'ali@example.com'})
# get_data('users')
