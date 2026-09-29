# client.py
import socket
import threading
import os
import sys
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, filedialog

from config import HOST, PORT, CHUNK_SIZE
from protocol import send_framed, recv_framed
from utils import calculate_sha256, verify_file_integrity


def play_alert():
    try:
        if sys.platform == "darwin":
            os.system("afplay /System/Library/Sounds/Ping.aiff &")
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
        self.incoming_files = {}  # file_id → file metadata & file object

        self._build_ui()
        self._connect()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def _build_ui(self):
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        self.chat = scrolledtext.ScrolledText(
            main,
            wrap=tk.WORD,
            state="disabled",
            bg="#313244",
            fg="#cdd6f4",
            font=("Segoe UI", 11),
            insertbackground="#cdd6f4",
            relief="flat",
            borderwidth=0,
        )
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        sidebar = tk.Frame(main, bg="#181825", width=180)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="Online Users",
            bg="#181825",
            fg="#cba6f7",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(10, 6))

        self.user_list = tk.Listbox(
            sidebar,
            bg="#313244",
            fg="#cdd6f4",
            font=("Segoe UI", 10),
            selectbackground="#89b4fa",
            selectforeground="#1e1e2e",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
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
            entry_frame,
            font=("Segoe UI", 11),
            bg="#313244",
            fg="#cdd6f4",
            insertbackground="#cdd6f4",
            relief="flat",
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=7)
        self.entry.bind("", self.send_message)
        self.entry.focus()

        tk.Button(
            entry_frame,
            text="📁",
            command=self.send_file_dialog,
            bg="#fab387",
            fg="#1e1e2e",
            font=("Segoe UI", 12, "bold"),
            relief="flat",
            padx=10,
            cursor="hand2",
        ).pack(side=tk.RIGHT, padx=(4, 0))

        tk.Button(
            entry_frame,
            text="Send",
            command=self.send_message,
            bg="#89b4fa",
            fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            cursor="hand2",
        ).pack(side=tk.RIGHT)

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            self.running = True
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.root.destroy()

    def safe_display(self, text: str, tag: str = "normal"):
        self.root.after(0, lambda: self._display(text, tag))

    def _display(self, text: str, tag: str):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, text + "\n", tag)
        self.chat.yview(tk.END)
        self.chat.config(state="disabled")

    def safe_update_users(self, users: list):
        self.root.after(0, lambda: self._update_users(users))

    def _update_users(self, users: list):
        self.user_list.delete(0, tk.END)
        for u in users:
            label = f"● {u} (You)" if u == self.username else f"● {u}"
            self.user_list.insert(tk.END, label)

    def receive_loop(self):
        while self.running:
            try:
                data = recv_framed(self.sock)
                if data is None:
                    break
                self.handle_message(data)
            except Exception:
                break

        if self.running:
            self.safe_display("*** Disconnected from server ***", "error")
            self.running = False

    def handle_message(self, data: dict):
        t = data.get("type")

        if t == "nick_request":
            send_framed(self.sock, {"type": "nick", "username": self.username})

        elif t in ("welcome", "system"):
            self.safe_display(data.get("text", ""), "system")

        elif t == "history":
            for msg in data.get("messages", []):
                self._render_history_item(msg)

        elif t == "users":
            self.safe_update_users(data.get("users", []))

        elif t == "chat":
            self.safe_display(f"{data['sender']}: {data['text']}", "normal")
            play_alert()

        elif t == "pm":
            self.safe_display(f"[PM from {data['from']}]: {data['text']}", "pm")
            play_alert()

        elif t == "pm_self":
            self.safe_display(f"[PM to {data['to']}]: {data['text']}", "pm")

        # Chunked File Handlers
        elif t == "file_offer":
            file_id = data["file_id"]
            sender = data["sender"]
            filename = data["filename"]
            size_mb = round(data["file_size"] / (1024 * 1024), 2)
            expected_hash = data["sha256"]

            accept = messagebox.askyesno(
                "Incoming File Offer",
                f"User '{sender}' wants to send you:\n\n{filename} ({size_mb} MB)\n\nAccept download?"
            )

            send_framed(self.sock, {"type": "file_response", "file_id": file_id, "accepted": accept})

            if accept:
                os.makedirs("downloads", exist_ok=True)
                save_path = os.path.join("downloads", f"received_{filename}")
                self.incoming_files[file_id] = {
                    "filename": filename,
                    "hash": expected_hash,
                    "path": save_path,
                    "file_obj": open(save_path, "wb")
                }
                self.safe_display(f"📥 Starting download for {filename}...", "file")

        elif t == "file_response":
            file_id = data.get("file_id")
            if data.get("accepted"):
                self.safe_display(f"✅ User accepted file transfer. Streaming chunks...", "file")
                threading.Thread(target=self._stream_file_chunks, args=(file_id,), daemon=True).start()
            else:
                self.safe_display(f"❌ User declined file transfer.", "error")

        elif t == "file_chunk":
            file_id = data["file_id"]
            if file_id in self.incoming_files:
                chunk_bytes = base64.b64decode(data["data_b64"])
                self.incoming_files[file_id]["file_obj"].write(chunk_bytes)

        elif t == "file_complete":
            file_id = data["file_id"]
            if file_id in self.incoming_files:
                info = self.incoming_files.pop(file_id)
                info["file_obj"].close()

                if verify_file_integrity(info["path"], info["hash"]):
                    self.safe_display(f"✅ Download complete & SHA-256 verified: downloads/{info['filename']}", "file")
                    play_alert()
                else:
                    self.safe_display(f"❌ File corruption detected for {info['filename']}", "error")

        elif t == "error":
            self.safe_display(f"*** {data.get('text', 'Unknown error')} ***", "error")

    def _render_history_item(self, msg: dict):
        t = msg.get("type")
        if t == "chat":
            self.safe_display(f"{msg.get('sender')}: {msg.get('text')}", "history")
        elif t == "system":
            self.safe_display(msg.get("text", ""), "history")

    def send_file_dialog(self):
        filepath = filedialog.askopenfilename(title="Select File to Send")
        if not filepath:
            return

        filename = os.path.basename(filepath)
        file_size = os.path.getsize(filepath)
        sha256 = calculate_sha256(filepath)

        self.pending_send_path = filepath
        send_framed(
            self.sock,
            {
                "type": "file_offer",
                "filename": filename,
                "file_size": file_size,
                "sha256": sha256
            }
        )
        self.safe_display(f"Offered file '{filename}' ({round(file_size/(1024*1024), 2)} MB). Waiting for receiver approval...", "self")

    def _stream_file_chunks(self, file_id: str):
        filepath = getattr(self, "pending_send_path", None)
        if not filepath or not os.path.exists(filepath):
            return

        chunk_idx = 0
        with open(filepath, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                b64_chunk = base64.b64encode(chunk).decode("utf-8")
                send_framed(
                    self.sock,
                    {
                        "type": "file_chunk",
                        "file_id": file_id,
                        "chunk_index": chunk_idx,
                        "data_b64": b64_chunk
                    }
                )
                chunk_idx += 1

        send_framed(self.sock, {"type": "file_complete", "file_id": file_id})
        self.safe_display(f"Finished uploading all chunks for {os.path.basename(filepath)}.", "self")

    def send_message(self, event=None):
        raw = self.entry.get().strip()
        if not raw or not self.running:
            return

        self.entry.delete(0, tk.END)

        try:
            if raw.startswith("/msg "):
                parts = raw.split(" ", 2)
                if len(parts) < 3:
                    self.safe_display("*** Usage: /msg   ***", "system")
                    return
                send_framed(
                    self.sock,
                    {"type": "pm", "target": parts[1], "text": parts[2]},
                )

            elif raw == "/help":
                self.safe_display(
                    "Commands:\n  /msg    → private message\n  /quit             → leave chat",
                    "system",
                )

            elif raw == "/quit":
                self.on_close()

            else:
                send_framed(self.sock, {"type": "chat", "text": raw})
                self.safe_display(f"You: {raw}", "self")

        except Exception:
            self.safe_display("[ERROR] Failed to send message.", "error")

    def on_close(self):
        self.running = False
        try:
            if self.sock:
                send_framed(self.sock, {"type": "quit"})
        except Exception:
            pass
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    ChatGUI()