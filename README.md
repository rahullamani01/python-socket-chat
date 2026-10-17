# 💬 Multi-Threaded Python Socket Chat

A real-time, multi-client chat application built with low-level TCP sockets, a custom binary protocol, a threaded server and a Tkinter desktop client with private messages, file transfer, voice notes and persistent chat history.

---

## 🚀 Features

**Server**
- **Multi-client chat** with one thread per client and a bounded send queue, so one slow client can never stall everyone else (slow clients are dropped).
- **Persistent chat history:** the last 50 messages are saved to disk and sent to every new user, even after a server restart.
- **Private messages** with `/msg <user> <text>`.
- **Chunked file transfer** with accept/decline, backpressure and SHA-256 verification.
- **Voice notes** broadcast to all users.
- **Heartbeat + idle timeout** to clean up dead connections.
- **Message logging** to `logs/chat_history.jsonl` (JSON Lines) and `logs/server.log`.

**Client (Tkinter)**
- Dark / light theme toggle.
- **Colored usernames** in chat and in the online-users sidebar (same user = same color everywhere).
- **Unread counter in the window title**, like `(3) Python Socket Chat`, while the window is unfocused.
- Desktop notifications and a sound alert for new messages.
- 📁 file sending: recipients get an accept/decline popup, files are saved to `downloads/`.
- 🎤 voice notes recorded from the microphone.
- Live online-users list and history replay on join.

---

## 🛠️ Tech Stack

| Part | Details |
|---|---|
| Language | Python 3.10+ |
| Networking | Standard `socket` library (TCP) |
| Concurrency | `threading`, `queue` |
| Serialization | `json` + raw binary frames |
| GUI | `tkinter` |
| Client extras | `plyer` (notifications), `sounddevice` + `numpy` (voice) |

The **server uses only the standard library**. Only the client needs extra packages.

---

## 📦 Protocol

Every message is one frame with an 8-byte big-endian header:

```text
+----------------+----------------+-----------------+------------------+
| json_len (4B)  | bin_len (4B)   | JSON payload    | raw binary bytes |
+----------------+----------------+-----------------+------------------+
```

- The length prefixes prevent TCP stream fragmentation and packet-stitching problems.
- File chunks travel as **raw bytes** in the binary part (no Base64, no +33% size overhead).
- Limits: JSON part up to 1 MB, binary part up to 4 MB per frame (file chunks are 64 KB).

### File transfer flow

```text
Sender                    Server                    Recipients
  | file_offer (+sha256) -> |                           |
  | <- file_offer_ack       | -- file_offer ----------> |
  |                         | <------- file_response -- |  (accept / decline)
  | <- file_go              |                           |
  | file_chunk x N -------> | -- file_chunk x N ------> |
  | file_complete --------> | -- file_complete -------> |  (checksum verified)
```

The server waits until every recipient has answered. If nobody accepts, the sender is told the transfer was declined. If the sender disconnects mid-transfer, recipients receive an abort and the partial file is deleted.

---

## ▶️ Getting Started

```bash
# 1. (optional) create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. install client dependencies
pip install plyer sounddevice numpy

# 3. start the server
python server.py

# 4. start one or more clients (new terminal for each)
python client.py
```

By default everything runs on `127.0.0.1:65433`. To chat across a network, change `HOST` in `config.py` (server) and `HOST` in `client.py` to the server's IP address.

---

## 💡 Usage

| Action | How |
|---|---|
| Send a message | Type and press Enter |
| Private message | `/msg <user> <text>` |
| Show commands | `/help` |
| Send a file | Click 📁 (max 50 MB, recipients must accept) |
| Send a voice note | Click 🎤 to start, ⏹️ to stop and send |
| Leave | `/quit` or close the window |

---

## 📁 Project Structure

```text
├── server.py      # Threaded server, history, file-transfer coordination
├── client.py      # Tkinter GUI client
├── protocol.py    # Frame encoding / decoding
├── config.py      # Host, port, history limit, log path
├── models.py      # Message dataclasses
├── utils.py       # Logging and SHA-256 helpers
├── tests/         # Protocol tests
└── logs/          # Generated at runtime (server.log, chat history)
```

---

## ⚠️ Notes & Limitations

- Voice notes are sent as Base64 inside JSON, so they are limited to about 700 KB (roughly 8 seconds).
- Private messages, voice notes and files are **not** stored in the replayed chat history.
- No encryption or authentication yet: usernames are first-come, first-served.
- Add `logs/` and `downloads/` to `.gitignore` so runtime files are not committed.

---

## 🗺️ Roadmap

- Timestamps on messages
- `/users`, `/clear` and message search commands
- Typing indicators
- TLS encryption and user accounts
