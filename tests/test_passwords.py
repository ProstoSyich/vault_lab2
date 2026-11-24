import pytest

from app.core.passwords import (
    WeakPasswordError,
    hash_password,
    validate_policy,
    verify_password,
)


def test_weak_password_rejected_by_length():
    with pytest.raises(WeakPasswordError):
        validate_policy("short")


def test_weak_password_rejected_by_zxcvbn():
    with pytest.raises(WeakPasswordError):
        validate_policy("password1234", user_inputs=["user@example.com"])


def test_password_matching_email_rejected():
    with pytest.raises(WeakPasswordError):
        validate_policy("User@example.com-1234", user_inputs=["user@example.com"])


def test_strong_password_accepted():
    validate_policy("correct-horse-battery-staple-42", user_inputs=["user@example.com"])


def test_hash_and_verify_roundtrip():
    hashed = hash_password("correct-horse-battery-staple-42")

    assert hashed.startswith("$argon2id$")
    assert hashed != "correct-horse-battery-staple-42"
    assert verify_password("correct-horse-battery-staple-42", hashed) is True
    assert verify_password("wrong-password-42", hashed) is False


def test_verify_handles_invalid_hash():
    assert verify_password("correct-horse-battery-staple-42", "not-a-hash") is False
