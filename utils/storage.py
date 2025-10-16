import json
import os
from cryptography.fernet import Fernet

DATA_DIR = "data"
KEY_DIR = os.path.join(DATA_DIR, "keys")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(KEY_DIR, exist_ok=True)

def _get_file(user_id):
    return os.path.join(DATA_DIR, f"{user_id}.json")

def _get_key_file(user_id):
    return os.path.join(KEY_DIR, f"{user_id}.key")

def _load_or_generate_key(user_id):
    key_path = _get_key_file(user_id)
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)
    return key

def _get_fernet(user_id):
    return Fernet(_load_or_generate_key(user_id))

def get_user_data(user_id):
    if user_id == "encrypted_data":
        print("Skipping system file: encrypted_data.json")
        return None

    path = _get_file(user_id)
    if not os.path.exists(path):
        return None

    fernet = _get_fernet(user_id)
    with open(path, "rb") as f:
        try:
            decrypted = fernet.decrypt(f.read()).decode()
            return json.loads(decrypted)
        except Exception as e:
            print(f"[ERROR] Failed to decrypt data for user {user_id}: {e}")
            return None  # Optionally: os.remove(path) to reset corrupted files

def save_user_data(user_id, data):
    path = _get_file(user_id)
    fernet = _get_fernet(user_id)
    try:
        encrypted = fernet.encrypt(json.dumps(data).encode())
        with open(path, "wb") as f:
            f.write(encrypted)
    except Exception as e:
        print(f"[ERROR] Failed to save data for user {user_id}: {e}")

def set_user_pin(user_id, pin):
    data = get_user_data(user_id) or {}
    data["pin"] = pin
    save_user_data(user_id, data)

def validate_user_pin(user_id, pin):
    data = get_user_data(user_id)
    if data is None:
        return False
    return data.get("pin") == pin
