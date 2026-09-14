# 💬 Multi-Threaded Python Socket Chat Application

A real-time, multi-client chat application built in Python using low-level TCP sockets, thread-safe message broadcasting, custom binary header framing, a Tkinter GUI client, and Base64-encoded media attachment transfers.

---

## 🚀 Features

* **Real-Time Multi-Client Communication:** Concurrent connection management using Python's `threading` library and explicit synchronization primitives (`threading.Lock`).
* **Custom Binary Protocol Framing:** Prevents TCP stream fragmentation and packet-stitching using a 4-byte Big-Endian length header preceding every JSON payload.
* **Base64 Media Pipeline:** In-band binary file transfer support for images and documents over text-based JSON socket streams.
* **Tkinter Graphical Client:** Fully event-driven user interface featuring a live online user list, direct active user tracking, scrollable message feeds, and binary attachment selectors.
* **Graceful Disconnect Management:** Clean handling of unexpected client termination and thread cleanup to preserve system resources.

---

## 🛠️ Tech Stack & Architecture

* **Language:** Python 3.10+
* **Networking:** Standard `socket` library (TCP/IP stack)
* **Concurrency:** `threading` (POSIX Threads wrapper)
* **Serialization:** `json` (Protocol layer) & `base64` (Binary-to-Text translation)
* **GUI Framework:** `tkinter` (Tk interface)

---

## 📦 System Architecture & Protocol

### Message Framing Model

TCP delivers a continuous, boundaryless byte stream. To maintain message integrity and isolate JSON payloads, all socket traffic uses a **4-byte fixed-length header** indicating payload byte size:

```text
+-------------------------+------------------------------------------------+
|  Header (4 Bytes)       |               Payload (Variable)               |
|  [ Big-Endian Length ]  |             {"type": "chat", ...}              |
+-------------------------+------------------------------------------------+
