from argon2 import PasswordHasher
from argon2 import exceptions as argon2_exceptions
from argon2.low_level import Type
from zxcvbn import zxcvbn

from app.config import settings


class WeakPasswordError(ValueError):
    pass


# Параметры OWASP для Argon2id: 3 итерации, 64 MiB памяти, 4 потока.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)


def _with_pepper(password: str) -> str:
    return password + settings.password_pepper


def hash_password(password: str) -> str:
    return _hasher.hash(_with_pepper(password))


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, _with_pepper(password))
    except (argon2_exceptions.VerificationError, argon2_exceptions.InvalidHashError):
        return False


def validate_policy(password: str, user_inputs: list[str] | None = None) -> None:
    if len(password) < settings.password_min_length:
        raise WeakPasswordError(
            f"Password must be at least {settings.password_min_length} characters long"
        )

    # zxcvbn учитывает словари и паттерны, а также не даёт использовать email в пароле.
    result = zxcvbn(password, user_inputs=list(user_inputs or []))
    if result["score"] < 3:
        raise WeakPasswordError(
            f"Password is too weak (score {result['score']}/4, minimum is 3)"
        )
