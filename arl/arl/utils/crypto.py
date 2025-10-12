from typing import Optional, List
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
import hashlib
import unicodedata


def _all_fernets() -> List[Fernet]:
    keys = [settings.FERNET_PRIMARY_KEY] + list(settings.FERNET_OLD_KEYS)
    return [Fernet(k.encode() if isinstance(k, str) else k) for k in keys if k]


def normalize_digits(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    return "".join(ch for ch in s if ch.isdigit())


def sin_encrypt(plaintext: str) -> str:
    d = normalize_digits(plaintext)
    if not d:
        return ""
    f = _all_fernets()[0]  # primary
    return f.encrypt(d.encode()).decode()


def sin_decrypt(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    for f in _all_fernets():
        try:
            return f.decrypt(token.encode()).decode()
        except InvalidToken:
            continue
    raise ValueError("Unable to decrypt SIN with available keys.")


def sin_last4(plaintext: str) -> str:
    d = normalize_digits(plaintext)
    return d[-4:] if len(d) >= 4 else d


def sin_hash(plaintext: str) -> str:
    d = normalize_digits(plaintext)
    salted = (settings.SIN_HASH_SALT + ":" + d).encode()
    return hashlib.sha256(salted).hexdigest()


def sin_luhn_valid(plaintext: str) -> bool:
    s = normalize_digits(plaintext)
    if len(s) != 9:
        return False
    total = 0
    for i, ch in enumerate(s):
        d = int(ch)
        if (i % 2) == 1:
            doubled = d * 2
            total += (doubled // 10) + (doubled % 10)
        else:
            total += d
    return (total % 10) == 0