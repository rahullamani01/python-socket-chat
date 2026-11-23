# Architecture and current boundaries

## Active code

Run the **root-level** `server.py` and `client.py`. The directories
`python-socket-chat-updated/` and `python.2/`, and the ZIP archive, are older
snapshots retained for reference. They are not the supported entry points or
part of the root test suite. Do not combine files from different snapshots.

## Components

```text
Tkinter client -- TCP frames --> threaded server <-- TCP frames -- Tkinter client
                                   |       |
                             room history  message/server logs
```

`client.py` owns its GUI and socket handling. `server.py` accepts connections,
starts a reader and a queued writer for each, tracks connected users and
coordinates broadcasts and file transfers. `protocol.py` encodes and receives
frames on the server; the client currently has its own framing implementation.
`config.py` holds server settings; client connection settings are in `client.py`.
`utils.py` contains logging and checksum helpers.

Each frame begins with two big-endian 32-bit lengths: JSON bytes and optional
binary bytes. Receivers read each section completely and enforce size limits.
File chunks use the binary section. The server forwards accepted transfers;
the receiving client checks the completed file's SHA-256 checksum. This detects
accidental corruption, not malicious tampering.

The server keeps up to 50 recent public chat and system events in memory.
It appends them to `logs/room_history.jsonl`, and loads and compacts that file
on startup. Private messages are not replayed but **are logged** in
`logs/chat_history.jsonl`; logs may contain sensitive data. Storage paths are
relative to the working directory. Back up data before experimenting.

## Known limitations and next steps

- No accounts, authentication, TLS, or protection from malicious peers.
- The server accepts untrusted file metadata without a server-side transfer
  size limit; clients should only be used on trusted networks.
- Client and server duplicate protocol and connection configuration.
- Tests do not yet cover GUI behavior, reconnects, concurrent load, failure
  paths for all transfers, or process-level restart behavior.
- Data files and historical snapshots are still tracked; cleanup requires a
  deliberate decision and care not to discard useful history.
- `models.py` is legacy scaffolding, not a complete authoritative schema.

Possible future milestones: isolate configuration and shared protocol, expand
integration tests, introduce database-backed accounts and rooms, add TLS, and
measure server performance. Preserve compatibility or document migrations.
