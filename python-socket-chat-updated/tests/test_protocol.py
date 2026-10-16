import socket
import threading
import unittest

from protocol import encode_frame, recv_framed


class ProtocolTests(unittest.TestCase):
    def test_json_frame_round_trip(self):
        left, right = socket.socketpair()
        try:
            expected = {"type": "chat", "sender": "Rahul", "text": "hello 🌍"}
            left.sendall(encode_frame(expected))
            self.assertEqual(recv_framed(right), expected)
        finally:
            left.close()
            right.close()

    def test_binary_frame_round_trip(self):
        left, right = socket.socketpair()
        try:
            expected = {"type": "file_chunk", "file_id": "abc123"}
            binary = bytes(range(256)) * 8
            left.sendall(encode_frame(expected, binary))
            actual = recv_framed(right)
            self.assertEqual({k: v for k, v in actual.items() if k != "_bin"}, expected)
            self.assertEqual(bytes(actual["_bin"]), binary)
        finally:
            left.close()
            right.close()

    def test_fragmented_header_and_payload(self):
        left, right = socket.socketpair()
        frame = encode_frame({"type": "ping"})

        def send_in_small_pieces():
            for byte in frame:
                left.sendall(bytes([byte]))
            left.close()

        try:
            worker = threading.Thread(target=send_in_small_pieces)
            worker.start()
            self.assertEqual(recv_framed(right), {"type": "ping"})
            worker.join(timeout=2)
        finally:
            right.close()


if __name__ == "__main__":
    unittest.main()
