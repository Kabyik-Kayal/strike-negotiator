from hashlib import sha256

from server.config import get_settings


def hash_worker_secret(worker_secret: str) -> str:
    salt = get_settings().hash_salt
    normalized = worker_secret.strip()
    return sha256(f"{normalized}:{salt}".encode("utf-8")).hexdigest()

