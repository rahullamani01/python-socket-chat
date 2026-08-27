import socket
import threading
import json
import sys
import os
import base64
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext, filedialog

HOST = "127.0.0.1"
PORT = 65433
HEADER_SIZE = 4


def send_framed(sock, data: dict):
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    header = len(payload).to_bytes(HEADER_SIZE, "big")
    sock.sendall(header + payload)


def recv_framed(sock):
    header = sock.recv(HEADER_SIZE)
    if len(header) < HEADER_SIZE:
        return None
    length = int.from_bytes(header, "big")
    if length <= 0 or length > 10_000_000:
        return None
    data = b""
    while len(data) < length:
        chunk = sock.recv(min(4096, length - len(data)))
        if not chunk:
            return None
        data += chunk
    return json.loads(data.decode("utf-8"))


def play_alert():
    try:
        if sys.platform == "darwin":
            os.system("afplay /System/Library/Sounds/Ping.aiff &")
        elif sys.platform.startswith("win"):
            import winsound
            winsound.MessageBeep()
    except Exception:
        pass


def file_to_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def base64_to_file(base64_str, output_path):
    file_bytes = base64.b64decode(base64_str.encode("utf-8"))
    with open(output_path, "wb") as f:
        f.write(file_bytes)


class ChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Python Socket Chat Room")
        self.root.geometry("740x580")
        self.root.configure(bg="#2c3e50")

        self.username = simpledialog.askstring("Username", "Choose your chat handle:", parent=self.root)
        if not self.username:
            self.root.destroy()
            return
        self.username = self.username.strip()[:32]

       
        main = tk.Frame(self.root, bg="#2c3e50")
        main.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.chat = scrolledtext.ScrolledText(
            main, wrap=tk.WORD, state="disabled", bg="#ecf0f1", fg="#2c3e50", font=("Helvetica", 11)
        )
        self.chat.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        sidebar = tk.Frame(main, bg="#34495e", width=160)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        tk.Label(sidebar, text="Active Users", bg="#34495e", fg="#ecf0f1", font=("Helvetica", 10, "bold")).pack(pady=5)
        
        self.user_list = tk.Listbox(sidebar, bg="#ecf0f1", fg="#2c3e50", font=("Helvetica", 10), selectbackground="#3498db")
        self.user_list.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        self.chat.tag_config("system", foreground="#7f8c8d", font=("Helvetica", 10, "italic"))
        self.chat.tag_config("pm", foreground="#8e44ad", font=("Helvetica", 11, "bold"))
        self.chat.tag_config("self", foreground="#2980b9", font=("Helvetica", 11, "bold"))
        self.chat.tag_config("normal", foreground="#2c3e50")
        self.chat.tag_config("error", foreground="#c0392b")

        # --- Controls ---
        entry_frame = tk.Frame(self.root, bg="#2c3e50")
        entry_frame.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.entry = tk.Entry(entry_frame, font=("Helvetica", 11))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.entry.bind("<Return>", self.send_message)

        tk.Button(
            entry_frame, text="📁 File", command=self.send_file_dialog, bg="#e67e22", fg="white", font=("Helvetica", 10, "bold")
        ).pack(side=tk.RIGHT, padx=(5, 0))

        tk.Button(
            entry_frame, text="Send", command=self.send_message, bg="#3498db", fg="white", font=("Helvetica", 10, "bold")
        ).pack(side=tk.RIGHT)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((HOST, PORT))
        except Exception as e:
            messagebox.showerror("Connection Error", str(e))
            self.root.destroy()
            return

        self.running = True
        threading.Thread(target=self.receive_loop, daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

   
    def safe_display(self, text, tag="normal"):
        self.root.after(0, lambda: self._display(text, tag))

    def _display(self, text, tag):
        self.chat.config(state="normal")
        self.chat.insert(tk.END, text + "\n", tag)
        self.chat.yview(tk.END)
        self.chat.config(state="disabled")

    def safe_update_users(self, users):
        self.root.after(0, lambda: self._update_users(users))

    def _update_users(self, users):
        self.user_list.delete(0, tk.END)
        for u in users:
            label = f"🟢 {u} (You)" if u == self.username else f"🟢 {u}"
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

    def handle_message(self, data):
        t = data.get("type")
        if t == "nick_request":
            send_framed(self.sock, {"type": "nick", "username": self.username})
        elif t in ("welcome", "system"):
            self.safe_display(data["text"], "system")
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
            sender = data["sender"]
            filename = data["filename"]
            save_dir = "downloads"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, f"received_{filename}")
            base64_to_file(data["file_data"], save_path)
            self.safe_display(f"📁 [{sender}] sent file: '{filename}' (Saved to downloads/)", "system")
            play_alert()
        elif t == "error":
            self.safe_display(f"*** {data['text']} ***", "error")

    # --- Senders ---
    def send_file_dialog(self):
        filepath = filedialog.askopenfilename(title="Select File to Send")
        if not filepath:
            return
        filename = os.path.basename(filepath)
        try:
            b64_data = file_to_base64(filepath)
            send_framed(self.sock, {"type": "file", "filename": filename, "file_data": b64_data})
            self.safe_display(f"You sent file: {filename}", "self")
        except Exception as e:
            self.safe_display(f"[ERROR] Could not send file: {e}", "error")

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
                send_framed(self.sock, {"type": "pm", "target": parts[1], "text": parts[2]})
            elif raw == "/help":
                self.safe_display("Commands: /msg <user> <text> | /quit", "system")
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
            send_framed(self.sock, {"type": "quit"})
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass
        self.root.destroy()


if __name__ == "__main__":
    ChatGUI()