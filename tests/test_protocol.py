import json
import socket
import struct
import threading
import unittest

from protocol import MAX_BINARY, MAX_JSON, ProtocolError, encode_frame, recv_framed


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.left, self.right = socket.socketpair()
        self.right.settimeout(2)
        self.addCleanup(self.left.close)
        self.addCleanup(self.right.close)

    def test_json_and_binary_round_trip(self):
        message = {"type": "chat", "text": "hello 🌍"}
        self.left.sendall(encode_frame(message, b"\x00\xff"))
        self.assertEqual(recv_framed(self.right), {**message, "_bin": bytearray(b"\x00\xff")})

    def test_fragmented_frame(self):
        frame = encode_frame({"type": "ping"}, b"data")
        def send():
            for byte in frame:
                self.left.sendall(bytes([byte]))
        worker = threading.Thread(target=send)
        worker.start()
        self.assertEqual(recv_framed(self.right), {"type": "ping", "_bin": bytearray(b"data")})
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())

    def test_coalesced_frames(self):
        self.left.sendall(encode_frame({"type": "ping"}) + encode_frame({"type": "quit"}))
        self.assertEqual(recv_framed(self.right), {"type": "ping"})
        self.assertEqual(recv_framed(self.right), {"type": "quit"})

    def test_rejects_invalid_lengths(self):
        for json_size, binary_size in [(0, 0), (MAX_JSON + 1, 0), (1, MAX_BINARY + 1)]:
            with self.subTest(json_size=json_size, binary_size=binary_size):
                self.left.sendall(struct.pack(">II", json_size, binary_size))
                with self.assertRaises(ProtocolError):
                    recv_framed(self.right)

    def test_rejects_non_object_json(self):
        body = json.dumps(["not", "an", "object"]).encode()
        self.left.sendall(struct.pack(">II", len(body), 0) + body)
        with self.assertRaises(ProtocolError):
            recv_framed(self.right)

    def test_eof_during_frame(self):
        self.left.sendall(struct.pack(">II", 10, 0) + b"{}")
        self.left.shutdown(socket.SHUT_WR)
        self.assertIsNone(recv_framed(self.right))
