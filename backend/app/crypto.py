from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings

_fernet = MultiFernet(
    [Fernet(key.strip().encode()) for key in settings.encryption_key.split(",") if key.strip()]
)


def encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Stored credential could not be decrypted") from exc