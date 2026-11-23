import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from protocol import recv_framed, send_framed


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.history_patch = patch.object(server, "ROOM_HISTORY_FILE", str(Path(self.temp.name) / "history.jsonl"))
        self.history_patch.start()
        self.addCleanup(self.history_patch.stop)
        self.log_patch = patch.object(server, "log_message")
        self.log_patch.start()
        self.addCleanup(self.log_patch.stop)
        server.message_history.clear()
        self.sockets = []
        self.threads = []
        self.addCleanup(self.close_clients)

    def close_clients(self):
        for sock in self.sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
        for thread in self.threads:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        server.message_history.clear()

    def connect(self, name):
        client, server_sock = socket.socketpair()
        client.settimeout(3)
        self.sockets.append(client)
        conn = server.Conn(server_sock, ("local", 0))
        thread = threading.Thread(target=server.handle_client, args=(conn,), daemon=True)
        thread.start()
        self.threads.append(thread)
        self.assertEqual(recv_framed(client)["type"], "nick_request")
        self.assertTrue(send_framed(client, {"type": "nick", "username": name}))
        self.assertEqual(self.receive_type(client, "welcome")["type"], "welcome")
        return client

    def receive_type(self, sock, kind):
        for _ in range(20):
            message = recv_framed(sock)
            self.assertIsNotNone(message)
            if message["type"] == kind:
                return message
        self.fail(f"Did not receive {kind}")

    def test_broadcast_and_private_message(self):
        alice = self.connect("Alice")
        bob = self.connect("Bob")
        send_framed(alice, {"type": "chat", "text": "Hello Bob"})
        self.assertEqual(self.receive_type(bob, "chat")["text"], "Hello Bob")
        send_framed(bob, {"type": "pm", "target": "Alice", "text": "Hi Alice"})
        self.assertEqual(self.receive_type(alice, "pm")["text"], "Hi Alice")
        self.assertEqual(self.receive_type(bob, "pm_self")["to"], "Alice")

    def test_history_persists_and_skips_corrupt_lines(self):
        server.add_history({"type": "chat", "sender": "Alice", "text": "saved"})
        path = Path(server.ROOM_HISTORY_FILE)
        with path.open("a", encoding="utf-8") as history:
            history.write("not json\n")
        server.message_history.clear()
        server.load_history()
        self.assertEqual(server.get_history_snapshot()[0]["text"], "saved")
        self.assertEqual(len([json.loads(line) for line in path.read_text().splitlines()]), 1)

    def test_late_joiner_receives_history(self):
        server.add_history({"type": "chat", "sender": "Alice", "text": "earlier"})
        client = self.connect("Bob")
        self.assertEqual(self.receive_type(client, "history")["messages"][0]["text"], "earlier")

    def test_file_offer_accept_and_binary_forwarding(self):
        alice = self.connect("Alice")
        bob = self.connect("Bob")
        send_framed(alice, {"type": "file_offer", "ref": "local-id", "filename": "test.txt",
                            "file_size": 3, "sha256": "example"})
        ack = self.receive_type(alice, "file_offer_ack")
        offer = self.receive_type(bob, "file_offer")
        self.assertEqual(ack["file_id"], offer["file_id"])
        fid = ack["file_id"]
        send_framed(bob, {"type": "file_response", "file_id": fid, "accepted": True})
        self.assertEqual(self.receive_type(alice, "file_go")["file_id"], fid)
        send_framed(alice, {"type": "file_chunk", "file_id": fid}, b"abc")
        self.assertEqual(bytes(self.receive_type(bob, "file_chunk")["_bin"]), b"abc")
        send_framed(alice, {"type": "file_complete", "file_id": fid})
        self.assertEqual(self.receive_type(bob, "file_complete")["file_id"], fid)
