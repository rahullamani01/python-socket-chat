import socket
import threading
import json
import os
import logging
from datetime import datetime
from collections import deque

# ==================== CONFIG ====================
HOST = "127.0.0.1"
PORT = 65433
LOG_FILE = "logs/chat_history.jsonl"
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 10 * 1024 * 1024   # 10 MB
HISTORY_LIMIT = 50

# ==================== GLOBALS ====================
clients = {}                  # sock → username
clients_lock = threading.Lock()
message_history = deque(maxlen=HISTORY_LIMIT)

# ==================== LOGGING ====================
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/server.log"),
        logging.StreamHandler()
    ]
)

# ==================== PROTOCOL ====================
def send_framed(sock, data: dict) -> bool:
    """Send length-prefixed JSON packet."""
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_MESSAGE_SIZE:
            return False
        header = len(payload).to_bytes(HEADER_SIZE, "big")
        sock.sendall(header + payload)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def recv_framed(sock):
    """Receive length-prefixed JSON packet."""
    try:
        header = b""
        while len(header) < HEADER_SIZE:
            chunk = sock.recv(HEADER_SIZE - len(header))
            if not chunk:
                return None
            header += chunk

        length = int.from_bytes(header, "big")
        if length <= 0 or length > MAX_MESSAGE_SIZE:
            return None

        data = b""
        while len(data) < length:
            chunk = sock.recv(min(4096, length - len(data)))
            if not chunk:
                return None
            data += chunk

        return json.loads(data.decode("utf-8"))
    except (ConnectionResetError, json.JSONDecodeError, OSError, ValueError):
        return None


# ==================== HELPERS ====================
def log_message(sender, recipient, content, msg_type="broadcast"):
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender": sender,
        "recipient": recipient,
        "type": msg_type,
        "content": content,
    }
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logging.error(f"Log write failed: {e}")


def broadcast(msg: dict, exclude=None):
    dead = []
    with clients_lock:
        targets = list(clients.keys())

    for sock in targets:
        if sock is exclude:
            continue
        if not send_framed(sock, msg):
            dead.append(sock)

    for sock in dead:
        remove_client(sock)


def broadcast_user_list():
    with clients_lock:
        users = sorted(clients.values())
    broadcast({"type": "users", "users": users})


def remove_client(sock):
    with clients_lock:
        username = clients.pop(sock, None)

    if username:
        try:
            sock.close()
        except OSError:
            pass

        leave_msg = {"type": "system", "text": f"*** {username} has left the chat. ***"}
        broadcast(leave_msg)
        message_history.append(leave_msg)
        broadcast_user_list()
        logging.info(f"[DISCONNECT] {username}")


# ==================== CLIENT HANDLER ====================
def handle_client(sock, addr):
    username = None
    try:
        # Ask for nickname
        send_framed(sock, {"type": "nick_request"})
        data = recv_framed(sock)

        if not data or data.get("type") != "nick" or not data.get("username"):
            return

        username = data["username"].strip()[:32]
        if not username:
            return

        # Check uniqueness
        with clients_lock:
            if username in clients.values():
                send_framed(sock, {"type": "error", "text": "Username already taken."})
                return
            clients[sock] = username

        logging.info(f"[REGISTERED] {addr} → '{username}'")

        # Welcome + send recent history
        send_framed(sock, {"type": "welcome", "text": f"Welcome to the server, {username}!"})
        if message_history:
            send_framed(sock, {"type": "history", "messages": list(message_history)})

        join_msg = {"type": "system", "text": f"*** {username} joined the chat! ***"}
        broadcast(join_msg, exclude=sock)
        message_history.append(join_msg)
        broadcast_user_list()

        # Main receive loop
        while True:
            data = recv_framed(sock)
            if data is None:
                break

            msg_type = data.get("type")

            if msg_type == "chat":
                text = data.get("text", "").strip()
                if text:
                    msg = {"type": "chat", "sender": username, "text": text}
                    broadcast(msg, exclude=sock)
                    message_history.append(msg)
                    log_message(username, "ALL", text, "broadcast")

            elif msg_type == "pm":
                target = data.get("target", "").strip()
                text = data.get("text", "").strip()

                if not target or not text:
                    send_framed(sock, {"type": "error", "text": "Usage: /msg <user> <message>"})
                    continue

                target_sock = None
                with clients_lock:
                    for s, name in clients.items():
                        if name == target:
                            target_sock = s
                            break

                if target_sock:
                    send_framed(target_sock, {"type": "pm", "from": username, "text": text})
                    send_framed(sock, {"type": "pm_self", "to": target, "text": text})
                    log_message(username, target, text, "private")
                else:
                    send_framed(sock, {"type": "error", "text": f"User '{target}' not found."})

            elif msg_type == "file":
                filename = data.get("filename")
                file_data = data.get("file_data")
                if filename and file_data:
                    msg = {
                        "type": "file",
                        "sender": username,
                        "filename": filename,
                        "file_data": file_data
                    }
                    broadcast(msg, exclude=sock)
                    log_message(username, "ALL", f"[FILE: {filename}]", "file")

            elif msg_type == "quit":
                break

    except Exception as e:
        logging.error(f"[ERROR] {username or addr}: {e}")
    finally:
        remove_client(sock)


# ==================== MAIN ====================
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    logging.info(f"[SERVER RUNNING] Listening on {HOST}:{PORT}")

    try:
        while True:
            client_sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        logging.info("\n[SERVER] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()