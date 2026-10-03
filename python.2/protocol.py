# protocol.py
"""
Frame layout (all big-endian):

  +----------------+----------------+-----------------+------------------+
  | json_len (4B)  | bin_len (4B)   | JSON payload    | raw binary bytes |
  +----------------+----------------+-----------------+------------------+

File chunks travel as raw bytes in the binary part (no Base64, no +33% size).
On receive, the binary part is exposed as msg["_bin"] (bytearray).
"""
import json
import socket
import struct

HEADER = struct.Struct(">II")
MAX_JSON = 1 * 1024 * 1024        # 1 MB cap on the JSON part
MAX_BINARY = 4 * 1024 * 1024      # 4 MB cap on a single binary part (chunks are ~64 KB)


class ProtocolError(Exception):
    pass


def encode_frame(msg: dict, binary: bytes = b"") -> bytes:
    """Build a frame once; the same bytes can be queued for many clients."""
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    return HEADER.pack(len(body), len(binary)) + body + binary


def send_framed(sock: socket.socket, msg: dict, binary: bytes = b"") -> bool:
    try:
        sock.sendall(encode_frame(msg, binary))
        return True
    except OSError:
        return False


def _recv_exact(sock: socket.socket, n: int):
    """Read exactly n bytes into one preallocated buffer. None on clean EOF."""
    if n == 0:
        return bytearray()
    buf = bytearray(n)
    view = memoryview(buf)
    got = 0
    while got < n:
        r = sock.recv_into(view[got:], n - got)
        if r == 0:
            return None
        got += r
    return buf


def recv_framed(sock: socket.socket):
    """Return a dict, or None if the peer closed the connection."""
    header = _recv_exact(sock, HEADER.size)
    if header is None:
        return None

    json_len, bin_len = HEADER.unpack(header)
    if json_len == 0 or json_len > MAX_JSON or bin_len > MAX_BINARY:
        raise ProtocolError(f"Frame too large or invalid ({json_len}, {bin_len})")

    body = _recv_exact(sock, json_len)
    if body is None:
        return None
    msg = json.loads(body)
    if not isinstance(msg, dict):
        raise ProtocolError("Payload must be a JSON object")

    if bin_len:
        blob = _recv_exact(sock, bin_len)
        if blob is None:
            return None
        msg["_bin"] = blob
    return msg