# utils/crypto.py
import os
from cryptography.fernet import Fernet

FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    raise RuntimeError("FERNET_KEY env var is not set. Generate using: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")

f = Fernet(FERNET_KEY.encode())

def encrypt_text(plaintext: str) -> str:
    return f.encrypt(plaintext.encode()).decode()

def decrypt_text(token: str) -> str:
    return f.decrypt(token.encode()).decode()
