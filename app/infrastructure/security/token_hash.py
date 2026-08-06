"""Hash raw tokens before storage — never persist plaintext tokens."""

import hashlib


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
