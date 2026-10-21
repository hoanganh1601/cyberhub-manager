"""Shared password hashing helpers for seed and authentication."""

"""Shared password hashing helpers for seed and authentication."""

import bcrypt


def hash_password(raw_password: str) -> str:
    """Hash a password using bcrypt and a random salt."""
    password_bytes = raw_password.encode("utf-8")

    if not password_bytes:
        raise ValueError("Password must not be empty.")

    if len(password_bytes) > 72:
        raise ValueError("Password must not exceed 72 UTF-8 bytes.")

    hashed = bcrypt.hashpw(
        password_bytes,
        bcrypt.gensalt(rounds=12),
    )

    return hashed.decode("ascii")


def verify_password(raw_password: str, password_hash: str) -> bool:
    """Check a password against a stored bcrypt hash."""
    password_bytes = raw_password.encode("utf-8")

    if not password_bytes or len(password_bytes) > 72:
        return False

    try:
        return bcrypt.checkpw(
            password_bytes,
            password_hash.encode("ascii"),
        )
    except ValueError:
        return False