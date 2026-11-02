"""Authentication behind a small interface.

To switch to company directory login (e.g. LDAP/AD), write a class with the same
`authenticate` method and assign it to `provider` below. Users still need a row in
the `users` table (matched by username) for roles and settings.
"""
import hashlib
import hmac
import os
from typing import Optional, Protocol

ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: Optional[str]) -> bool:
    try:
        _, it, salt, digest = (stored or "").split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(it))
    return hmac.compare_digest(dk.hex(), digest)


class AuthProvider(Protocol):
    def authenticate(self, conn, username: str, password: str) -> Optional[int]:
        """Return the user id on success, else None."""


class LocalAuthProvider:
    def authenticate(self, conn, username, password):
        u = conn.execute("SELECT id, password_hash FROM users WHERE username=?",
                         (username,)).fetchone()
        if u and verify_password(password, u["password_hash"]):
            return u["id"]
        return None


provider: AuthProvider = LocalAuthProvider()
