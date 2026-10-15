# server.py
import socket
import threading
import queue
import uuid
import logging
from collections import deque

from config import HOST, PORT, HISTORY_LIMIT
from protocol import encode_frame, recv_framed
from utils import setup_logging, log_message

setup_logging()

SEND_QUEUE_MAX = 512        # frames buffered per client before it is dropped as "too slow"
IDLE_TIMEOUT = 60           # seconds without any frame (clients ping every 20s)
FILE_BLOCK_TIMEOUT = 30     # backpressure wait when a receiver is slow during a file transfer
MAX_TEXT = 4000

clients = {}                # username -> Conn   (O(1) lookup, O(1) uniqueness check)
clients_lock = threading.Lock()
message_history = deque(maxlen=HISTORY_LIMIT)

transfers = {}              # file_id -> transfer state
transfers_lock = threading.Lock()


class Conn:
    """One client: socket + bounded outgoing queue + dedicated writer thread.
    Broadcasting only enqueues bytes, so one slow client can never stall the others."""

    def __init__(self, sock, addr):
        self.sock = sock
        self.addr = addr
        self.name = None
        self.alive = True
        self.q = queue.Queue(maxsize=SEND_QUEUE_MAX)
        threading.Thread(target=self._writer, daemon=True).start()

    def send(self, frame: bytes, block: bool = False) -> bool:
        if not self.alive:
            return False
        try:
            if block:
                self.q.put(frame, timeout=FILE_BLOCK_TIMEOUT)
            else:
                self.q.put_nowait(frame)
            return True
        except queue.Full:
            logging.warning(f"[SLOW CLIENT] dropping {self.name or self.addr}")
            self.close()
            return False

    def send_msg(self, msg: dict, binary: bytes = b"") -> bool:
        return self.send(encode_frame(msg, binary))

    def _writer(self):
        while True:
            frame = self.q.get()
            if frame is None:
                break
            try:
                self.sock.sendall(frame)
            except OSError:
                break
        self.close()

    def close(self):
        if not self.alive:
            return
        self.alive = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        try:
            self.q.put_nowait(None)
        except queue.Full:
            pass


# ---------------------------------------------------------------- broadcasting
def broadcast(msg: dict, exclude=None):
    frame = encode_frame(msg)  # encode ONCE, share the bytes with every client
    with clients_lock:
        targets = list(clients.values())
    for c in targets:
        if c is not exclude:
            c.send(frame)


def broadcast_user_list():
    with clients_lock:
        users = sorted(clients.keys())
    broadcast({"type": "users", "users": users})


# ---------------------------------------------------------------- file transfers
def _start_or_cancel(fid, t):
    """Call with transfers_lock held, once every recipient has answered."""
    if t["accepted"]:
        t["started"] = True
        t["sender"].send_msg({"type": "file_go", "file_id": fid})
    else:
        transfers.pop(fid, None)
        t["sender"].send_msg({"type": "file_declined", "file_id": fid})


def _cleanup_transfers(conn):
    with transfers_lock:
        for fid, t in list(transfers.items()):
            if t["sender"] is conn:
                del transfers[fid]
                for r in t["accepted"]:
                    r.send_msg({"type": "file_abort", "file_id": fid})
            elif conn in t["pending"] or conn in t["accepted"]:
                t["pending"].discard(conn)
                if conn in t["accepted"]:
                    t["accepted"].remove(conn)
                if not t["started"] and not t["pending"]:
                    _start_or_cancel(fid, t)


# ---------------------------------------------------------------- lifecycle
def remove_client(conn):
    with clients_lock:
        registered = conn.name is not None and clients.get(conn.name) is conn
        if registered:
            del clients[conn.name]
    conn.close()
    _cleanup_transfers(conn)

    if registered:
        leave = {"type": "system", "text": f"*** {conn.name} has left the chat. ***"}
        message_history.append(leave)
        broadcast(leave)
        broadcast_user_list()
        logging.info(f"[DISCONNECT] {conn.name}")


def handle_client(conn: Conn):
    sock = conn.sock
    username = None
    try:
        conn.send_msg({"type": "nick_request"})
        data = recv_framed(sock)
        if not data or data.get("type") != "nick":
            return

        username = str(data.get("username", "")).strip()[:32]
        if not username:
            return

        with clients_lock:
            if username in clients:
                conn.send_msg({"type": "error", "text": "Username already taken."})
                return
            clients[username] = conn
            conn.name = username

        logging.info(f"[REGISTERED] {conn.addr} -> '{username}'")

        conn.send_msg({"type": "welcome", "text": f"Welcome to the server, {username}!"})
        if message_history:
            conn.send_msg({"type": "history", "messages": list(message_history)})

        join = {"type": "system", "text": f"*** {username} joined the chat! ***"}
        message_history.append(join)
        broadcast(join, exclude=conn)
        broadcast_user_list()

        while True:
            data = recv_framed(sock)
            if data is None:
                break
            t = data.get("type")

            if t == "ping":
                continue

            elif t == "chat":
                text = str(data.get("text", "")).strip()[:MAX_TEXT]
                if text:
                    msg = {"type": "chat", "sender": username, "text": text}
                    message_history.append(msg)
                    broadcast(msg, exclude=conn)
                    log_message(username, "ALL", text, "broadcast")

            elif t == "pm":
                target = str(data.get("target", "")).strip()
                text = str(data.get("text", "")).strip()[:MAX_TEXT]
                if not target or not text:
                    conn.send_msg({"type": "error", "text": "Usage: /msg <user> <message>"})
                    continue
                with clients_lock:
                    target_conn = clients.get(target)
                if target_conn:
                    target_conn.send_msg({"type": "pm", "from": username, "text": text})
                    conn.send_msg({"type": "pm_self", "to": target, "text": text})
                    log_message(username, target, text, "private")
                else:
                    conn.send_msg({"type": "error", "text": f"User '{target}' not found."})

            # ---- file transfer ------------------------------------------------
            elif t == "file_offer":
                size = data.get("file_size")
                if not isinstance(size, int) or size < 0:
                    conn.send_msg({"type": "error", "text": "Invalid file offer."})
                    continue
                with clients_lock:
                    recipients = [c for c in clients.values() if c is not conn]
                if not recipients:
                    conn.send_msg({"type": "error", "text": "No one else is online."})
                    continue

                fid = uuid.uuid4().hex
                with transfers_lock:
                    transfers[fid] = {
                        "sender": conn,
                        "pending": set(recipients),
                        "accepted": [],
                        "started": False,
                    }
                # ack goes first so the sender can map ref -> file_id before file_go arrives
                conn.send_msg({"type": "file_offer_ack", "file_id": fid, "ref": data.get("ref")})
                offer = encode_frame({
                    "type": "file_offer",
                    "file_id": fid,
                    "sender": username,
                    "filename": str(data.get("filename", "file"))[:255],
                    "file_size": size,
                    "sha256": str(data.get("sha256", "")),
                })
                for r in recipients:
                    r.send(offer)

            elif t == "file_response":
                fid = data.get("file_id")
                accepted = bool(data.get("accepted"))
                with transfers_lock:
                    tr = transfers.get(fid)
                    if tr and not tr["started"] and conn in tr["pending"]:
                        tr["pending"].discard(conn)
                        if accepted:
                            tr["accepted"].append(conn)
                        if not tr["pending"]:
                            _start_or_cancel(fid, tr)

            elif t == "file_chunk":
                fid = data.get("file_id")
                with transfers_lock:
                    tr = transfers.get(fid)
                    targets = list(tr["accepted"]) if tr and tr["sender"] is conn and tr["started"] else []
                if targets:
                    frame = encode_frame({"type": "file_chunk", "file_id": fid}, data.get("_bin", b""))
                    for r in targets:
                        r.send(frame, block=True)   # backpressure: slows the sender instead of dropping

            elif t == "file_complete":
                fid = data.get("file_id")
                with transfers_lock:
                    tr = transfers.get(fid)
                    if tr and tr["sender"] is conn:
                        del transfers[fid]
                    else:
                        tr = None
                if tr:
                    frame = encode_frame({"type": "file_complete", "file_id": fid})
                    for r in tr["accepted"]:
                        r.send(frame, block=True)
                    log_message(username, "ALL", f"[FILE TRANSFERRED: {fid}]", "file")

            elif t == "quit":
                break

    except Exception as e:
        logging.error(f"[ERROR] {username or conn.addr}: {e}")
    finally:
        remove_client(conn)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(128)
    logging.info(f"[SERVER RUNNING] Listening on {HOST}:{PORT}")

    try:
        while True:
            sock, addr = server.accept()
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.settimeout(IDLE_TIMEOUT)
            conn = Conn(sock, addr)
            threading.Thread(target=handle_client, args=(conn,), daemon=True).start()
    except KeyboardInterrupt:
        logging.info("[SERVER] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()