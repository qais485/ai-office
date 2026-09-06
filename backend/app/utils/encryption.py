from cryptography.fernet import Fernet
from app.core.config import settings


def get_cipher() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        raise ValueError("ENCRYPTION_KEY not configured")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_field(value: str) -> str:
    if not value:
        return value
    cipher = get_cipher()
    return cipher.encrypt(value.encode()).decode()


def decrypt_field(value: str) -> str:
    if not value:
        return value
    cipher = get_cipher()
    return cipher.decrypt(value.encode()).decode()


def generate_key() -> str:
    return Fernet.generate_key().decode()
