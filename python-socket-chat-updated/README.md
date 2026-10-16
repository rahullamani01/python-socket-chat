# 💬 Multi-Threaded Python Socket Chat Application

A real-time multi-client chat application built with Python TCP sockets, threads, a Tkinter GUI, private messages, message history, voice notes, and small file attachments.

## Features

- **Multi-client TCP chat:** the server handles each connected client in a dedicated thread.
- **Length-prefixed framing:** every frame starts with an 8-byte header containing two big-endian unsigned integers: JSON payload length (4 bytes), followed by binary payload length (4 bytes). This handles TCP stream fragmentation and coalescing correctly.
- **JSON messages:** chat, private messages, user lists, history, system notices, and control messages use JSON.
- **Private messages:** send `/msg <username> <message>`.
- **Keep-alive heartbeat:** the client sends a `ping` every 20 seconds so an idle connection does not hit the server's 60-second timeout.
- **Voice notes:** record and send WAV voice notes using Base64 JSON messages.
- **Small file attachments:** Base64 attachments are limited to about 700 KiB because Base64 increases payload size and the JSON frame limit is 1 MiB.
- **Dark/light themes:** switch the Tkinter interface theme from the sidebar.
- **Logging and history:** server logs connection events and appends message metadata to the configured JSONL log.

## Requirements

- Python 3.10+
- `numpy`, `sounddevice`, and `plyer` for the GUI's audio/notification features
- Tkinter (usually included with Python)

Install optional dependencies with:

```bash
python -m pip install numpy sounddevice plyer
```

## Run locally

Open two terminals in the project directory.

Terminal 1:
```bash
python server.py
```

Terminal 2 (repeat in another terminal for more clients):
```bash
python client.py
```

The default server address is `127.0.0.1:65433`, which is local-machine only. To connect from other devices, configure the server bind address and firewall/network settings deliberately. Do not expose this unauthenticated chat server directly to the public internet.

## Protocol framing

```text
+----------------------+----------------------+-------------------+-------------------+
| JSON length (4 B)    | Binary length (4 B)  | JSON bytes        | Binary bytes      |
| unsigned big-endian  | unsigned big-endian  | variable length   | variable length   |
+----------------------+----------------------+-------------------+-------------------+
```

TCP is a byte stream, not a message protocol. Receivers must read the complete header and then the exact number of bytes declared by each length. The protocol module also supports a raw binary part, although the current GUI sends voice notes and small attachments inside JSON using Base64.

## Current limitations

- The application does not authenticate users or encrypt traffic. Use only on trusted networks until TLS and authentication are added.
- Message history is currently in memory for the running server; the JSONL log is a separate append-only record.
- Base64 attachments are intended for small files. A future upgrade should use the server's chunked binary transfer messages end-to-end for larger files.
