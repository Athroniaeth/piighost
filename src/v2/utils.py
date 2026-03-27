import hashlib


def hash_sha256(text: str) -> str:
    """SHA-256 hash of a text string."""
    return hashlib.sha256(text.encode()).hexdigest()
