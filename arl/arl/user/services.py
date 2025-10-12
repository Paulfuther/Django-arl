# arl/user/services.py
from typing import Optional
from arl.utils.crypto import normalize_digits, sin_encrypt, sin_last4, sin_hash


# If you already have sin_luhn_valid in arl.utils.crypto, import it:
try:
    from arl.utils.crypto import sin_luhn_valid
except ImportError:
    # lightweight fallback; remove if you already have it
    def sin_luhn_valid(plaintext: str) -> bool:
        s = "".join(ch for ch in plaintext or "" if ch.isdigit())
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


def set_user_sin(user, plaintext: Optional[str], *,
                 validate_luhn: bool = True, save: bool = True):
    """
    Normalizes and encrypts a SIN, updating the user's encrypted fields.
    Never stores plaintext.
    """
    d = normalize_digits(plaintext or "")
    user.sin_encrypted = sin_encrypt(d) if d else ""
    user.sin_last4 = sin_last4(d) if d else ""
    user.sin_hash = sin_hash(d) if d else ""
    if save:
        user.save(update_fields=["sin_encrypted", "sin_last4", "sin_hash"])
    return user