"""Local account storage. Not yet connected to the chat protocol.

Passwords are hashed with scrypt and per-account random salts. This module does
not provide transport security, rate limiting, or an authentication service.
"""
import hashlib
import hmac
import os
import re
import sqlite3

USERNAME = re.compile(r"[A-Za-z0-9_]{3,32}\Z", re.ASCII)
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
HASH_BYTES = 32


class AccountError(ValueError):
    """An account name or password does not meet the local policy."""


class AccountStore:
    def __init__(self, path):
        self.path = os.fspath(path)
        with sqlite3.connect(self.path) as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS accounts (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    scrypt_n INTEGER NOT NULL,
                    scrypt_r INTEGER NOT NULL,
                    scrypt_p INTEGER NOT NULL
                )"""
            )

    @staticmethod
    def _validate(username, password):
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            raise AccountError("Username must be 3–32 ASCII letters, numbers or underscores.")
        if not isinstance(password, str) or not 12 <= len(password) <= 128:
            raise AccountError("Password must be 12–128 characters.")

    @staticmethod
    def _hash(password, salt, n, r, p):
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=HASH_BYTES)

    def register(self, username, password):
        """Create an account; return False if its case-insensitive name exists."""
        self._validate(username, password)
        salt = os.urandom(SALT_BYTES)
        digest = self._hash(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
        try:
            with sqlite3.connect(self.path) as db:
                db.execute("INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?)",
                           (username, salt, digest, SCRYPT_N, SCRYPT_R, SCRYPT_P))
        except sqlite3.IntegrityError:
            return False
        return True

    def authenticate(self, username, password):
        """Return the canonical username on success, otherwise None."""
        try:
            self._validate(username, password)
        except AccountError:
            return None
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT username, salt, password_hash, scrypt_n, scrypt_r, scrypt_p "
                "FROM accounts WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
        if row is None:
            # Also perform scrypt for unknown users to reduce username timing leaks.
            self._hash(password, b"\0" * SALT_BYTES, SCRYPT_N, SCRYPT_R, SCRYPT_P)
            return None
        canonical, salt, expected, n, r, p = row
        candidate = self._hash(password, salt, n, r, p)
        return canonical if hmac.compare_digest(candidate, expected) else None
