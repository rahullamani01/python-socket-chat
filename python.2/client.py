import socket
import threading
import json
import sys
import os
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, filedialog

# ==================== CONFIG ====================
HOST = "127.0.0.1"
PORT = 65433
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_FILE_SIZE = 5 * 1024 * 1024       # 5 MB

# ==================== PROTOCOL ====================
def send_framed(sock, data: dict) -> bool:
    try:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_MESSAGE_SIZE:
            return False
        header = len(payload).to_bytes(HEADER_SIZE, "big")
        sock.sendall(header + payload)
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def recv_framed(sock):
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


# ==================== HELPERS ====================
def play_alert():
    try:
        if sys.platform == "darwin":
            os.system("afplay /System/Library/Sounds/Ping.aiff &")
        elif sys.platform.startswith("win"):
            import winsound
            winsound.MessageBeep()
    except Exception:
        pass


def file_to_base64(file_path: str) -> str:
    size = os.path.getsize(file_path)
    if size > MAX_FILE_SIZE:
        raise ValueError(f"File too large (max {MAX_FILE_SIZE // 1024 // 1024} MB)")
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def base64_to_file(base64_str: str, output_path: str):
    file_bytes = base64.b64decode(base64_str.encode("utf-8"))
    with open(output_path, "wb") as f:
        f.write(file_bytes)


# ==================== GUI ====================
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

        self._build_ui()
        self._connect()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def _build_ui(self):
        # Main container
        main = tk.Frame(self.root, bg="#1e1e2e")
        main.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        # Chat area
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

        # Sidebar
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

        # Message tags
        self.chat.tag_config("system", foreground="#a6adc8", font=("Segoe UI", 10, "italic"))
        self.chat.tag_config("pm", foreground="#cba6f7", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("self", foreground="#89b4fa", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("normal", foreground="#cdd6f4")
        self.chat.tag_config("error", foreground="#f38ba8")
        self.chat.tag_config("file", foreground="#a6e3a1")
        self.chat.tag_config("history", foreground="#7f849c", font=("Segoe UI", 10, "italic"))

        # Input area
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
        self.entry.bind("<Return>", self.send_message)
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

    # ---------- Thread-safe UI helpers ----------
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

    # ---------- Networking ----------
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
            # Show previous messages when joining
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

        elif t == "file":
            sender = data.get("sender", "Unknown")
            filename = data.get("filename", "file")
            save_dir = "downloads"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"received_{filename}")
            try:
                base64_to_file(data["file_data"], save_path)
                self.safe_display(
                    f"📁 [{sender}] sent file: {filename} → downloads/", "file"
                )
                play_alert()
            except Exception as e:
                self.safe_display(f"[ERROR] Failed to save file: {e}", "error")

        elif t == "error":
            self.safe_display(f"*** {data.get('text', 'Unknown error')} ***", "error")

    def _render_history_item(self, msg: dict):
        t = msg.get("type")
        if t == "chat":
            self.safe_display(f"{msg.get('sender')}: {msg.get('text')}", "history")
        elif t == "system":
            self.safe_display(msg.get("text", ""), "history")

    # ---------- Sending ----------
    def send_file_dialog(self):
        filepath = filedialog.askopenfilename(title="Select File to Send")
        if not filepath:
            return

        filename = os.path.basename(filepath)
        try:
            b64_data = file_to_base64(filepath)
            send_framed(
                self.sock,
                {"type": "file", "filename": filename, "file_data": b64_data},
            )
            self.safe_display(f"You sent file: {filename}", "self")
        except Exception as e:
            self.safe_display(f"[ERROR] {e}", "error")

    def send_message(self, event=None):
        raw = self.entry.get().strip()
        if not raw or not self.running:
            return

        self.entry.delete(0, tk.END)

        try:
            if raw.startswith("/msg "):
                parts = raw.split(" ", 2)
                if len(parts) < 3:
                    self.safe_display("*** Usage: /msg <username> <message> ***", "system")
                    return
                send_framed(
                    self.sock,
                    {"type": "pm", "target": parts[1], "text": parts[2]},
                )

            elif raw == "/help":
                self.safe_display(
                    "Commands:\n  /msg <user> <text>  → private message\n  /quit             → leave chat",
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