import sqlite3
import tempfile
import unittest
from pathlib import Path

from accounts import AccountError, AccountStore


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "accounts.sqlite3"
        self.store = AccountStore(self.path)

    def test_registration_and_persistent_login(self):
        self.assertTrue(self.store.register("Alice", "a strong password"))
        self.assertEqual(AccountStore(self.path).authenticate("alice", "a strong password"), "Alice")
        self.assertIsNone(self.store.authenticate("Alice", "wrong password"))
        self.assertIsNone(self.store.authenticate("unknown", "a strong password"))

    def test_duplicate_names_are_case_insensitive(self):
        self.assertTrue(self.store.register("Alice", "a strong password"))
        self.assertFalse(self.store.register("ALICE", "another password"))
        self.assertEqual(self.store.authenticate("Alice", "a strong password"), "Alice")

    def test_invalid_registration(self):
        for username, password in [("ab", "a strong password"), ("a b", "a strong password"),
                                   ("valid_name", "short"), ("valid_name", "x" * 129)]:
            with self.subTest(username=username, password=password):
                with self.assertRaises(AccountError):
                    self.store.register(username, password)

    def test_passwords_are_salted_and_not_stored_as_plaintext(self):
        password = "a strong password"
        self.store.register("Alice", password)
        self.store.register("Bob", password)
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT salt, password_hash FROM accounts ORDER BY username").fetchall()
        self.assertNotEqual(rows[0][0], rows[1][0])
        self.assertNotEqual(rows[0][1], rows[1][1])
        self.assertNotIn(password.encode(), self.path.read_bytes())
