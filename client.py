# client.py
import os
import sys
import socket
import threading
import queue
import subprocess
import uuid
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, filedialog

from config import HOST, PORT, CHUNK_SIZE
from protocol import send_framed, recv_framed
from utils import calculate_sha256, verify_file_integrity

HEARTBEAT_MS = 20_000
POLL_MS = 30


def play_alert():
    try:
        if sys.platform == "darwin":
            subprocess.Popen(
                ["afplay", "/System/Library/Sounds/Ping.aiff"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        elif sys.platform.startswith("win"):
            import winsound
            winsound.MessageBeep()
    except Exception:
        pass


class ChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Python Socket Chat")
        self.root.geometry("780x600")
        self.root.configure(bg="#1e1e2e")
        self.root.minsize(600, 450)

        self.username = simpledialog.askstring(
            "Username", "Choose your chat handle:", parent=self.root
        )
        if not self.username:
            self.root.destroy()
            return
        self.username = self.username.strip()[:32]

        self.sock = None
        self.running = False
        self.send_lock = threading.Lock()      # GUI thread + upload thread share the socket
        self.inbox = queue.Queue()             # network thread -> GUI thread
        self.incoming_files = {}               # file_id -> {filename, hash, path, file_obj}
        self.offer_refs = {}                   # ref -> local path (waiting for server ack)
        self.pending_sends = {}                # file_id -> local path (offer acknowledged)

        self._build_ui()
        self._connect()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(POLL_MS, self._poll)
        self.root.after(HEARTBEAT_MS, self._heartbeat)
        self.root.mainloop()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        self.chat = scrolledtext.ScrolledText(
            main, wrap=tk.WORD, state="disabled", bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 11), insertbackground="#cdd6f4", relief="flat", borderwidth=0,
        )
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        sidebar = tk.Frame(main, bg="#181825", width=180)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="Online Users", bg="#181825", fg="#cba6f7",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(10, 6))

        self.user_list = tk.Listbox(
            sidebar, bg="#313244", fg="#cdd6f4", font=("Segoe UI", 10),
            selectbackground="#89b4fa", selectforeground="#1e1e2e",
            relief="flat", borderwidth=0, highlightthickness=0,
        )
        self.user_list.pack(padx=8, pady=(0, 8), fill=tk.BOTH, expand=True)

        self.chat.tag_config("system", foreground="#a6adc8", font=("Segoe UI", 10, "italic"))
        self.chat.tag_config("pm", foreground="#cba6f7", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("self", foreground="#89b4fa", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("normal", foreground="#cdd6f4")
        self.chat.tag_config("error", foreground="#f38ba8")
        self.chat.tag_config("file", foreground="#a6e3a1")
        self.chat.tag_config("history", foreground="#7f849c", font=("Segoe UI", 10, "italic"))

        entry_frame = tk.Frame(self.root, bg="#1e1e2e")
        entry_frame.pack(padx=12, pady=(0, 12), fill=tk.X)

        self.entry = tk.Entry(
            entry_frame, font=("Segoe UI", 11), bg="#313244", fg="#cdd6f4",
            insertbackground="#cdd6f4", relief="flat",
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=7)
        self.entry.bind("<Return>", self.send_message)
        self.entry.focus()

        tk.Button(
            entry_frame, text="📁", command=self.send_file_dialog, bg="#fab387", fg="#1e1e2e",
            font=("Segoe UI", 12, "bold"), relief="flat", padx=10, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            entry_frame, text="Send", command=self.send_message, bg="#89b4fa", fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=16, cursor="hand2",
        ).pack(side=tk.RIGHT)

    def _display(self, text: str, tag: str = "normal"):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, text + "\n", tag)
        self.chat.yview(tk.END)
        self.chat.config(state="disabled")

    def _update_users(self, users: list):
        self.user_list.delete(0, tk.END)
        for u in users:
            self.user_list.insert(tk.END, f"● {u} (You)" if u == self.username else f"● {u}")

    # ------------------------------------------------------------------ networking
    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.connect((HOST, PORT))
            self.running = True
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.root.destroy()

    def _send(self, msg: dict, binary: bytes = b"") -> bool:
        if not self.sock:
            return False
        with self.send_lock:
            return send_framed(self.sock, msg, binary)

    def _local(self, text: str, tag: str = "normal"):
        """Thread-safe: queue a line for the GUI thread to display."""
        self.inbox.put({"type": "_local", "text": text, "tag": tag})

    def _heartbeat(self):
        if self.running:
            self._send({"type": "ping"})
            self.root.after(HEARTBEAT_MS, self._heartbeat)

    def receive_loop(self):
        """Runs in the network thread. Never touches Tk widgets.
        File bytes are written to disk right here; everything else goes to the GUI via the queue."""
        while self.running:
            try:
                data = recv_framed(self.sock)
                if data is None:
                    break
                t = data.get("type")
                if t == "file_chunk":
                    self._on_chunk(data)
                elif t == "file_complete":
                    self._on_complete(data)
                else:
                    self.inbox.put(data)
            except Exception:
                break
        self.inbox.put({"type": "_disconnected"})

    def _on_chunk(self, data: dict):
        info = self.incoming_files.get(data.get("file_id"))
        if info:
            try:
                info["file_obj"].write(data.get("_bin", b""))
            except (ValueError, OSError):
                pass

    def _on_complete(self, data: dict):
        info = self.incoming_files.pop(data.get("file_id"), None)
        if not info:
            return
        try:
            info["file_obj"].close()
        except OSError:
            pass
        # hashing a big file must not block the socket reader
        threading.Thread(target=self._verify_download, args=(info,), daemon=True).start()

    def _verify_download(self, info: dict):
        if verify_file_integrity(info["path"], info["hash"]):
            self._local(f"✅ Download complete & SHA-256 verified: {info['path']}", "file")
            self.inbox.put({"type": "_alert"})
        else:
            self._local(f"❌ File corruption detected for {info['filename']}", "error")

    # ------------------------------------------------------------------ GUI-thread dispatch
    def _poll(self):
        for _ in range(100):  # bounded work per tick keeps the UI responsive
            try:
                item = self.inbox.get_nowait()
            except queue.Empty:
                break
            self._dispatch(item)
        self.root.after(POLL_MS, self._poll)

    def _dispatch(self, data: dict):
        t = data.get("type")

        if t == "_local":
            self._display(data["text"], data.get("tag", "normal"))

        elif t == "_alert":
            play_alert()

        elif t == "_disconnected":
            if self.running:
                self._display("*** Disconnected from server ***", "error")
                self.running = False

        elif t == "nick_request":
            self._send({"type": "nick", "username": self.username})

        elif t in ("welcome", "system"):
            self._display(data.get("text", ""), "system")

        elif t == "history":
            for msg in data.get("messages", []):
                if msg.get("type") == "chat":
                    self._display(f"{msg.get('sender')}: {msg.get('text')}", "history")
                elif msg.get("type") == "system":
                    self._display(msg.get("text", ""), "history")

        elif t == "users":
            self._update_users(data.get("users", []))

        elif t == "chat":
            self._display(f"{data['sender']}: {data['text']}", "normal")
            play_alert()

        elif t == "pm":
            self._display(f"[PM from {data['from']}]: {data['text']}", "pm")
            play_alert()

        elif t == "pm_self":
            self._display(f"[PM to {data['to']}]: {data['text']}", "pm")

        elif t == "file_offer":
            self._handle_offer(data)

        elif t == "file_offer_ack":
            path = self.offer_refs.pop(data.get("ref"), None)
            if path:
                self.pending_sends[data["file_id"]] = path

        elif t == "file_go":
            path = self.pending_sends.pop(data.get("file_id"), None)
            if path:
                self._display("✅ Receiver(s) accepted. Streaming file...", "file")
                threading.Thread(
                    target=self._stream_file, args=(data["file_id"], path), daemon=True
                ).start()

        elif t == "file_declined":
            self.pending_sends.pop(data.get("file_id"), None)
            self._display("❌ Everyone declined the file transfer.", "error")

        elif t == "file_abort":
            info = self.incoming_files.pop(data.get("file_id"), None)
            if info:
                try:
                    info["file_obj"].close()
                    os.remove(info["path"])
                except OSError:
                    pass
                self._display(f"❌ Transfer of {info['filename']} was cancelled by the sender.", "error")

        elif t == "error":
            self._display(f"*** {data.get('text', 'Unknown error')} ***", "error")

    # ------------------------------------------------------------------ file receive
    def _handle_offer(self, data: dict):
        fid = data["file_id"]
        filename = os.path.basename(str(data.get("filename", "file"))) or "file"  # blocks ../ path tricks
        size_mb = round(data.get("file_size", 0) / (1024 * 1024), 2)

        accept = messagebox.askyesno(
            "Incoming File Offer",
            f"User '{data.get('sender')}' wants to send you:\n\n{filename} ({size_mb} MB)\n\nAccept download?",
        )

        if accept:
            os.makedirs("downloads", exist_ok=True)
            path = os.path.join("downloads", f"{fid[:8]}_{filename}")  # unique name, never overwrites
            try:
                fobj = open(path, "wb")
            except OSError as e:
                self._display(f"❌ Cannot save file: {e}", "error")
                accept = False
            else:
                # register BEFORE replying so no chunk can arrive for an unknown file
                self.incoming_files[fid] = {
                    "filename": filename, "hash": data.get("sha256", ""),
                    "path": path, "file_obj": fobj,
                }
                self._display(f"📥 Downloading {filename}...", "file")

        self._send({"type": "file_response", "file_id": fid, "accepted": accept})

    # ------------------------------------------------------------------ file send
    def send_file_dialog(self):
        filepath = filedialog.askopenfilename(title="Select File to Send")
        if not filepath or not self.running:
            return
        self._display(f"Preparing '{os.path.basename(filepath)}'...", "self")
        threading.Thread(target=self._offer_file, args=(filepath,), daemon=True).start()

    def _offer_file(self, filepath: str):
        try:
            sha256 = calculate_sha256(filepath)          # off the GUI thread
            size = os.path.getsize(filepath)
        except OSError as e:
            self._local(f"❌ Cannot read file: {e}", "error")
            return

        ref = uuid.uuid4().hex
        self.offer_refs[ref] = filepath
        self._send({
            "type": "file_offer", "ref": ref,
            "filename": os.path.basename(filepath),
            "file_size": size, "sha256": sha256,
        })
        self._local(
            f"Offered '{os.path.basename(filepath)}' ({round(size / (1024 * 1024), 2)} MB). "
            "Waiting for approval...", "self",
        )

    def _stream_file(self, file_id: str, filepath: str):
        name = os.path.basename(filepath)
        try:
            total = os.path.getsize(filepath)
            sent = 0
            last_mark = 0
            idx = 0
            with open(filepath, "rb") as f:
                while self.running:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    # raw bytes in the binary part of the frame - no Base64
                    if not self._send({"type": "file_chunk", "file_id": file_id, "idx": idx}, chunk):
                        raise OSError("connection lost")
                    idx += 1
                    sent += len(chunk)
                    mark = (sent * 100 // total) // 25 * 25 if total else 100
                    if mark > last_mark:
                        last_mark = mark
                        self._local(f"📤 {name}: {mark}%", "file")
            self._send({"type": "file_complete", "file_id": file_id})
            self._local(f"Finished uploading {name}.", "self")
        except OSError as e:
            self._local(f"❌ Upload of {name} failed: {e}", "error")

    # ------------------------------------------------------------------ chat input
    def send_message(self, event=None):
        raw = self.entry.get().strip()
        if not raw or not self.running:
            return
        self.entry.delete(0, tk.END)

        if raw.startswith("/msg "):
            parts = raw.split(" ", 2)
            if len(parts) < 3:
                self._display("*** Usage: /msg <user> <message> ***", "system")
                return
            self._send({"type": "pm", "target": parts[1], "text": parts[2]})

        elif raw == "/help":
            self._display(
                "Commands:\n  /msg <user> <message> → private message\n  /quit → leave chat",
                "system",
            )

        elif raw == "/quit":
            self.on_close()

        else:
            if self._send({"type": "chat", "text": raw}):
                self._display(f"You: {raw}", "self")
            else:
                self._display("[ERROR] Failed to send message.", "error")

    def on_close(self):
        self.running = False
        try:
            if self.sock:
                self._send({"type": "quit"})
                self.sock.close()
        except Exception:
            pass
        for info in list(self.incoming_files.values()):
            try:
                info["file_obj"].close()
            except OSError:
                pass
        self.root.destroy()


if __name__ == "__main__":
    ChatGUI()