# chat/protocol.py
import json
import socket
from typing import Optional, Dict, Any
from config import HEADER_SIZE, MAX_MESSAGE_SIZE


def send_framed(sock: socket.socket, data: Dict[str, Any]) -> bool:
    """Send a length-prefixed JSON message."""
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_MESSAGE_SIZE:
            return False
        header = len(payload).to_bytes(HEADER_SIZE, "big")
        sock.sendall(header + payload)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def recv_framed(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """Receive a length-prefixed JSON message."""
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