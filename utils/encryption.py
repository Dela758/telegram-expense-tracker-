import base64
import json
from cryptography.fernet import Fernet, InvalidToken
import os

KEYS_DIR = "data/keys"
DATA_DIR = "data"

def ensure_dirs():
    os.makedirs(KEYS_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

def user_key_path(user_id: str) -> str:
    return os.path.join(KEYS_DIR, f"{user_id}.key")

def generate_user_key(user_id: str):
    ensure_dirs()
    key = Fernet.generate_key()
    with open(user_key_path(user_id), "wb") as f:
        f.write(key)

def load_user_key(user_id: str) -> bytes:
    key_path = user_key_path(user_id)
    if not os.path.exists(key_path):
        generate_user_key(user_id)
    with open(key_path, "rb") as f:
        return f.read()

def get_fernet_for_user(user_id: str) -> Fernet:
    key = load_user_key(user_id)
    return Fernet(key)

def encrypt_data_for_user(data: dict, user_id: str) -> bytes:
    fernet = get_fernet_for_user(user_id)
    json_str = json.dumps(data)
    return fernet.encrypt(json_str.encode())

def decrypt_data_for_user(encrypted_bytes: bytes, user_id: str) -> dict:
    fernet = get_fernet_for_user(user_id)
    json_str = fernet.decrypt(encrypted_bytes).decode()
    return json.loads(json_str)

def save_encrypted_file_for_user(data: dict, user_id: str):
    ensure_dirs()
    encrypted = encrypt_data_for_user(data, user_id)
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    with open(file_path, "wb") as f:
        f.write(encrypted)

def load_encrypted_file_for_user(user_id: str) -> dict:
    file_path = os.path.join(DATA_DIR, f"{user_id}.json")
    if not os.path.exists(file_path):
        # No file yet, return empty data
        return {}

    try:
        if os.path.getsize(file_path) == 0:
            print(f"[WARNING] Empty data file for user {user_id}")
            return {}

        with open(file_path, "rb") as f:
            encrypted_bytes = f.read()

        # Try decrypting to verify integrity
        data = decrypt_data_for_user(encrypted_bytes, user_id)
        return data

    except InvalidToken:
        print(f"[ERROR] Failed to decrypt data for user {user_id}: Invalid token or wrong key.")
        return {}

    except Exception as e:
        print(f"[ERROR] Unexpected error loading data for user {user_id}: {e}")
        return {}
