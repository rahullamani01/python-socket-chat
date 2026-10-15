import socket
import threading
import json
import sys
import os
import base64
import tempfile
import wave
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, filedialog
from plyer import notification
import sounddevice as sd
import numpy as np

# ==================== CONFIG ====================
HOST = "127.0.0.1"
PORT = 65433
HEADER_SIZE = 4
MAX_MESSAGE_SIZE = 10 * 1024 * 1024
MAX_FILE_SIZE = 5 * 1024 * 1024
SAMPLE_RATE = 44100
CHANNELS = 1

# ==================== THEMES ====================
THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "sidebar": "#181825",
        "chat_bg": "#313244",
        "fg": "#cdd6f4",
        "accent": "#89b4fa",
        "purple": "#cba6f7",
        "green": "#a6e3a1",
        "red": "#f38ba8",
        "orange": "#fab387",
        "muted": "#a6adc8",
        "history": "#7f849c",
        "entry_bg": "#313244",
        "button_fg": "#1e1e2e",
        "voice": "#f9e2af",
    },
    "light": {
        "bg": "#f5f5f5",
        "sidebar": "#e0e0e0",
        "chat_bg": "#ffffff",
        "fg": "#1e1e2e",
        "accent": "#1e88e5",
        "purple": "#7b1fa2",
        "green": "#2e7d32",
        "red": "#c62828",
        "orange": "#ef6c00",
        "muted": "#616161",
        "history": "#9e9e9e",
        "entry_bg": "#ffffff",
        "button_fg": "#ffffff",
        "voice": "#f9a825",
    }
}

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


def show_notification(title: str, message: str):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="Python Socket Chat",
            timeout=4
        )
    except Exception:
        pass


# ==================== GUI ====================
class ChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Python Socket Chat")
        self.root.geometry("820x620")
        self.root.minsize(650, 480)

        self.current_theme = "dark"
        self.theme = THEMES[self.current_theme]

        self.username = simpledialog.askstring(
            "Username", "Choose your chat handle:", parent=self.root
        )
        if not self.username:
            self.root.destroy()
            return
        self.username = self.username.strip()[:32]

        self.sock = None
        self.running = False
        self.window_focused = True

        # Voice recording state
        self.is_recording = False
        self.recording_data = []
        self.stream = None

        self._build_ui()
        self._apply_theme()
        self._connect()

        self.root.bind("<FocusIn>", lambda e: setattr(self, "window_focused", True))
        self.root.bind("<FocusOut>", lambda e: setattr(self, "window_focused", False))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def _build_ui(self):
        self.main = tk.Frame(self.root)
        self.main.pack(padx=12, pady=12, fill=tk.BOTH, expand=True)

        # Chat area
        self.chat = scrolledtext.ScrolledText(
            self.main,
            wrap=tk.WORD,
            state="disabled",
            font=("Segoe UI", 11),
            relief="flat",
            borderwidth=0,
        )
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Sidebar
        self.sidebar = tk.Frame(self.main, width=180)
        self.sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.sidebar_title = tk.Label(
            self.sidebar,
            text="Online Users",
            font=("Segoe UI", 11, "bold"),
        )
        self.sidebar_title.pack(pady=(10, 6))

        self.user_list = tk.Listbox(
            self.sidebar,
            font=("Segoe UI", 10),
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
        )
        self.user_list.pack(padx=8, pady=(0, 8), fill=tk.BOTH, expand=True)

        # Theme toggle
        self.theme_btn = tk.Button(
            self.sidebar,
            text="☀️ Light Mode",
            command=self.toggle_theme,
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            cursor="hand2",
        )
        self.theme_btn.pack(pady=(0, 10), padx=8, fill=tk.X)

        # Tags
        self.chat.tag_config("system", font=("Segoe UI", 10, "italic"))
        self.chat.tag_config("pm", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("self", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("normal")
        self.chat.tag_config("error")
        self.chat.tag_config("file")
        self.chat.tag_config("voice", font=("Segoe UI", 11, "bold"))
        self.chat.tag_config("history", font=("Segoe UI", 10, "italic"))

        # Input area
        self.entry_frame = tk.Frame(self.root)
        self.entry_frame.pack(padx=12, pady=(0, 12), fill=tk.X)

        self.entry = tk.Entry(
            self.entry_frame,
            font=("Segoe UI", 11),
            relief="flat",
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), ipady=7)
        self.entry.bind("<Return>", self.send_message)
        self.entry.focus()

        # Voice button
        self.voice_btn = tk.Button(
            self.entry_frame,
            text="🎤",
            command=self.toggle_recording,
            font=("Segoe UI", 12, "bold"),
            relief="flat",
            padx=10,
            cursor="hand2",
        )
        self.voice_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # File button
        self.file_btn = tk.Button(
            self.entry_frame,
            text="📁",
            command=self.send_file_dialog,
            font=("Segoe UI", 12, "bold"),
            relief="flat",
            padx=10,
            cursor="hand2",
        )
        self.file_btn.pack(side=tk.RIGHT, padx=(4, 0))

        # Send button
        self.send_btn = tk.Button(
            self.entry_frame,
            text="Send",
            command=self.send_message,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=16,
            cursor="hand2",
        )
        self.send_btn.pack(side=tk.RIGHT)

    def _apply_theme(self):
        t = self.theme

        self.root.configure(bg=t["bg"])
        self.main.configure(bg=t["bg"])
        self.entry_frame.configure(bg=t["bg"])

        self.chat.configure(bg=t["chat_bg"], fg=t["fg"], insertbackground=t["fg"])
        self.sidebar.configure(bg=t["sidebar"])
        self.sidebar_title.configure(bg=t["sidebar"], fg=t["purple"])
        self.user_list.configure(
            bg=t["chat_bg"],
            fg=t["fg"],
            selectbackground=t["accent"],
            selectforeground=t["button_fg"]
        )

        self.entry.configure(bg=t["entry_bg"], fg=t["fg"], insertbackground=t["fg"])
        self.file_btn.configure(bg=t["orange"], fg=t["button_fg"])
        self.voice_btn.configure(bg=t["voice"], fg=t["button_fg"])
        self.send_btn.configure(bg=t["accent"], fg=t["button_fg"])
        self.theme_btn.configure(bg=t["sidebar"], fg=t["fg"])

        self.chat.tag_config("system", foreground=t["muted"])
        self.chat.tag_config("pm", foreground=t["purple"])
        self.chat.tag_config("self", foreground=t["accent"])
        self.chat.tag_config("normal", foreground=t["fg"])
        self.chat.tag_config("error", foreground=t["red"])
        self.chat.tag_config("file", foreground=t["green"])
        self.chat.tag_config("voice", foreground=t["voice"])
        self.chat.tag_config("history", foreground=t["history"])

        if self.current_theme == "dark":
            self.theme_btn.config(text="☀️ Light Mode")
        else:
            self.theme_btn.config(text="🌙 Dark Mode")

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.theme = THEMES[self.current_theme]
        self._apply_theme()

    def _connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((HOST, PORT))
            self.running = True
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.root.destroy()

    # ---------- Voice Recording ----------
    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        self.is_recording = True
        self.recording_data = []
        self.voice_btn.config(text="⏹️", bg="#f38ba8")

        def callback(indata, frames, time, status):
            if self.is_recording:
                self.recording_data.append(indata.copy())

        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='float32',
                callback=callback
            )
            self.stream.start()
            self.safe_display("🎤 Recording... Click ⏹️ to stop & send", "system")
        except Exception as e:
            self.is_recording = False
            self.voice_btn.config(text="🎤")
            self.safe_display(f"[ERROR] Microphone error: {e}", "error")

    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        self.voice_btn.config(text="🎤")
        self._apply_theme()  # restore color

        if not self.recording_data:
            self.safe_display("*** No audio recorded ***", "system")
            return

        try:
            audio = np.concatenate(self.recording_data, axis=0)

            # Save to temporary wav file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            with wave.open(tmp_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(SAMPLE_RATE)
                # Convert float32 → int16
                audio_int16 = (audio * 32767).astype(np.int16)
                wf.writeframes(audio_int16.tobytes())

            # Send as voice note
            b64_data = file_to_base64(tmp_path)
            send_framed(self.sock, {
                "type": "voice",
                "filename": "voice_note.wav",
                "file_data": b64_data
            })
            self.safe_display("🎤 You sent a voice note", "self")

            os.unlink(tmp_path)

        except Exception as e:
            self.safe_display(f"[ERROR] Failed to send voice note: {e}", "error")

    def play_voice_note(self, filepath: str):
        try:
            with wave.open(filepath, 'rb') as wf:
                data = wf.readframes(wf.getnframes())
                audio = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767
                sd.play(audio, SAMPLE_RATE)
        except Exception as e:
            self.safe_display(f"[ERROR] Could not play voice note: {e}", "error")

    # ---------- UI Helpers ----------
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
            for msg in data.get("messages", []):
                self._render_history_item(msg)

        elif t == "users":
            self.safe_update_users(data.get("users", []))

        elif t == "chat":
            sender = data['sender']
            text = data['text']
            self.safe_display(f"{sender}: {text}", "normal")
            play_alert()
            if not self.window_focused and sender != self.username:
                show_notification(f"Message from {sender}", text)

        elif t == "pm":
            sender = data['from']
            text = data['text']
            self.safe_display(f"[PM from {sender}]: {text}", "pm")
            play_alert()
            if not self.window_focused:
                show_notification(f"Private message from {sender}", text)

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
                self.safe_display(f"📁 [{sender}] sent file: {filename} → downloads/", "file")
                play_alert()
                if not self.window_focused:
                    show_notification(f"File from {sender}", filename)
            except Exception as e:
                self.safe_display(f"[ERROR] Failed to save file: {e}", "error")

        elif t == "voice":
            sender = data.get("sender", "Unknown")
            save_dir = "downloads"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"voice_{sender}_{os.getpid()}.wav")
            try:
                base64_to_file(data["file_data"], save_path)
                self.safe_display(f"🎤 [{sender}] sent a voice note (playing...)", "voice")
                play_alert()
                # Play in background
                threading.Thread(target=self.play_voice_note, args=(save_path,), daemon=True).start()

                if not self.window_focused:
                    show_notification(f"Voice note from {sender}", "Click to listen")
            except Exception as e:
                self.safe_display(f"[ERROR] Failed to play voice note: {e}", "error")

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
        try:
            b64_data = file_to_base64(filepath)
            send_framed(self.sock, {
                "type": "file",
                "filename": filename,
                "file_data": b64_data
            })
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
                send_framed(self.sock, {
                    "type": "pm",
                    "target": parts[1],
                    "text": parts[2]
                })

            elif raw == "/help":
                self.safe_display(
                    "Commands:\n"
                    "  /msg <user> <text>  → private message\n"
                    "  /quit               → leave chat\n"
                    "  🎤 button           → record voice note",
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
        if self.is_recording:
            self.stop_recording()
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