from auth import normalize_token


def authenticate(token: str) -> bool:
    return normalize_token(token) == 'valid'
