import hmac
from hashlib import sha256

from server.config import get_settings


def hash_worker_secret(worker_secret: str) -> str:
    salt = get_settings().hash_salt.encode("utf-8")
    normalized = worker_secret.strip().encode("utf-8")
    return hmac.new(salt, normalized, sha256).hexdigest()
