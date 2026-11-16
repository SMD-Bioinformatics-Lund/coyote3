# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Password hashing owned by the API credential boundary."""

from werkzeug.security import generate_password_hash


def hash_password(password: str) -> str:
    """Hash a local password with the application's existing PBKDF2 policy.

    Args:
        password: Plaintext supplied through an authorized credential operation.

    Returns:
        Salted Werkzeug PBKDF2-HMAC-SHA256 storage representation.
    """
    return str(generate_password_hash(password, method="pbkdf2:sha256"))
