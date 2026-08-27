import socket
import threading
import json
import os
from datetime import datetime

HOST = "127.0.0.1"
PORT = 65433
LOG_FILE = "chat_history.jsonl"
HEADER_SIZE = 4

clients = {}  
clients_lock = threading.Lock()


def send_framed(sock, data: dict):
    """Sends a 4-byte length-prefixed JSON packet."""
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        header = len(payload).to_bytes(HEADER_SIZE, "big")
        sock.sendall(header + payload)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def recv_framed(sock):
    """Receives a 4-byte length-prefixed JSON packet (up to 10MB for file support)."""
    try:
        header = sock.recv(HEADER_SIZE)
        if len(header) < HEADER_SIZE:
            return None
        length = int.from_bytes(header, "big")
        if length <= 0 or length > 10_000_000: 
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
        print(f"[LOG ERROR] {e}")


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
        broadcast({"type": "system", "text": f"*** {username} has left the chat. ***"})
        broadcast_user_list()
        print(f"[DISCONNECT] {username}")


def handle_client(sock, addr):
    username = None
    try:
      
        send_framed(sock, {"type": "nick_request"})
        data = recv_framed(sock)
        if not data or data.get("type") != "nick" or not data.get("username"):
            return
        username = data["username"].strip()[:32]
        if not username:
            return

        with clients_lock:
            if username in clients.values():
                send_framed(sock, {"type": "error", "text": "Username already taken."})
                return
            clients[sock] = username

        print(f"[REGISTERED] {addr} → '{username}'")
        broadcast({"type": "system", "text": f"*** {username} joined the chat! ***"}, exclude=sock)
        send_framed(sock, {"type": "welcome", "text": f"Welcome to the server, {username}!"})
        broadcast_user_list()

       
        while True:
            data = recv_framed(sock)
            if data is None:
                break

            msg_type = data.get("type")

            if msg_type == "chat":
                text = data.get("text", "").strip()
                if text:
                    broadcast({"type": "chat", "sender": username, "text": text}, exclude=sock)
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
                    broadcast(
                        {"type": "file", "sender": username, "filename": filename, "file_data": file_data},
                        exclude=sock
                    )
                    log_message(username, "ALL", f"[FILE: {filename}]", "file")

            elif msg_type == "quit":
                break

    except Exception as e:
        print(f"[ERROR] {username or addr}: {e}")
    finally:
        remove_client(sock)


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVER RUNNING] Listening on {HOST}:{PORT}...")

    try:
        while True:
            client_sock, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
    finally:
        server.close()


if __name__ == "__main__":
    main()