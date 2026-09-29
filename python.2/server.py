# server.py
import socket
import threading
import json
import os
import uuid
import logging
from collections import deque

from config import HOST, PORT, HISTORY_LIMIT
from protocol import send_framed, recv_framed
from utils import setup_logging, log_message

setup_logging()

# Global state tracking
clients = {}                  # sock → username
clients_lock = threading.Lock()
message_history = deque(maxlen=HISTORY_LIMIT)
active_transfers = {}         # file_id → {"sender_sock": sock, "recipients": list}


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

        logging.info(f"[REGISTERED] {addr} → '{username}'")

        send_framed(sock, {"type": "welcome", "text": f"Welcome to the server, {username}!"})
        if message_history:
            send_framed(sock, {"type": "history", "messages": list(message_history)})

        join_msg = {"type": "system", "text": f"*** {username} joined the chat! ***"}
        broadcast(join_msg, exclude=sock)
        message_history.append(join_msg)
        broadcast_user_list()

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
                    send_framed(sock, {"type": "error", "text": "Usage: /msg  "})
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

            # Binary Chunked Transfer Handlers
            elif msg_type == "file_offer":
                file_id = str(uuid.uuid4())
                data["file_id"] = file_id
                data["sender"] = username
                active_transfers[file_id] = {"sender_sock": sock, "accepted_socks": []}
                broadcast(data, exclude=sock)

            elif msg_type == "file_response":
                file_id = data.get("file_id")
                accepted = data.get("accepted", False)
                transfer = active_transfers.get(file_id)

                if transfer:
                    if accepted:
                        transfer["accepted_socks"].append(sock)
                    # Tell sender to start streaming chunks
                    send_framed(transfer["sender_sock"], data)

            elif msg_type == "file_chunk":
                file_id = data.get("file_id")
                transfer = active_transfers.get(file_id)
                if transfer:
                    # Forward chunk only to clients who accepted
                    for recipient_sock in transfer["accepted_socks"]:
                        send_framed(recipient_sock, data)

            elif msg_type == "file_complete":
                file_id = data.get("file_id")
                transfer = active_transfers.pop(file_id, None)
                if transfer:
                    for recipient_sock in transfer["accepted_socks"]:
                        send_framed(recipient_sock, data)
                    log_message(username, "ALL", f"[FILE TRANSFERRED: {file_id}]", "file")

            elif msg_type == "quit":
                break

    except Exception as e:
        logging.error(f"[ERROR] {username or addr}: {e}")
    finally:
        remove_client(sock)


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