import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

from transport import client_context, server_context


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL command required for test certificate")
class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.cert = str(Path(cls.temp.name) / "cert.pem")
        cls.key = str(Path(cls.temp.name) / "key.pem")
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", cls.key, "-out", cls.cert, "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost",
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def exchange(self, hostname):
        left, right = socket.socketpair()
        left.settimeout(5)
        right.settimeout(5)
        errors = []

        def serve():
            try:
                with server_context(self.cert, self.key).wrap_socket(left, server_side=True) as sock:
                    sock.sendall(b"ok")
            except (OSError, ssl.SSLError) as exc:
                errors.append(exc)

        worker = threading.Thread(target=serve)
        worker.start()
        try:
            with client_context(self.cert).wrap_socket(right, server_hostname=hostname) as sock:
                return sock.recv(2)
        finally:
            right.close()
            worker.join(timeout=6)
            self.assertFalse(worker.is_alive())

    def test_verified_connection(self):
        self.assertEqual(self.exchange("localhost"), b"ok")

    def test_hostname_mismatch_is_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.exchange("wrong.example")

    def test_certificate_and_key_are_required(self):
        with self.assertRaises(ValueError):
            server_context("", "")
