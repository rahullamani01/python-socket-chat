import socket
import threading
import os
import sys
import hashlib
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext

HOST = '127.0.0.1'
PORT = 65433

SECRET_KEY = "chat_secret_key"  # Default shared secret key

def encrypt_message(plain_text, key=SECRET_KEY):
    key_hash = hashlib.sha256(key.encode('utf-8')).digest()
    encrypted_bytes = bytearray()
    for i, char in enumerate(plain_text.encode('utf-8')):
        encrypted_bytes.append(char ^ key_hash[i % len(key_hash)])
    return encrypted_bytes.hex()

def decrypt_message(hex_text, key=SECRET_KEY):
    try:
        key_hash = hashlib.sha256(key.encode('utf-8')).digest()
        encrypted_bytes = bytes.fromhex(hex_text)
        decrypted_bytes = bytearray()
        for i, byte in enumerate(encrypted_bytes):
            decrypted_bytes.append(byte ^ key_hash[i % len(key_hash)])
        return decrypted_bytes.decode('utf-8')
    except Exception:
        return "[Decryption Error: Invalid Secret Key or Corrupted Packet]"

def play_alert_sound():
    try:
        if sys.platform == 'darwin':
            os.system('afplay /System/Library/Sounds/Ping.aiff &')
        elif sys.platform.startswith('win'):
            import winsound
            winsound.MessageBeep()
    except:
        pass

class ChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Python Socket Chat Room [E2E Encrypted]")
        self.root.geometry("480x580")
        self.root.configure(bg="#2c3e50")

        self.username = simpledialog.askstring("Username", "Choose your chat handle:", parent=self.root)
        if not self.username:
            self.root.destroy()
            return

        self.chat_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, state='disabled', bg="#ecf0f1", fg="#2c3e50", font=("Helvetica", 11)
        )
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        self.chat_area.tag_config("system", foreground="#7f8c8d", font=("Helvetica", 10, "italic"))
        self.chat_area.tag_config("pm", foreground="#8e44ad", font=("Helvetica", 11, "bold"))
        self.chat_area.tag_config("self", foreground="#2980b9", font=("Helvetica", 11, "bold"))
        self.chat_area.tag_config("normal", foreground="#2c3e50", font=("Helvetica", 11))

        self.entry_frame = tk.Frame(self.root, bg="#2c3e50")
        self.entry_frame.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.msg_entry = tk.Entry(self.entry_frame, font=("Helvetica", 11))
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.msg_entry.bind("<Return>", self.send_message)

        self.send_btn = tk.Button(
            self.entry_frame, text="Send", command=self.send_message, bg="#3498db", fg="white", font=("Helvetica", 10, "bold")
        )
        self.send_btn.pack(side=tk.RIGHT)

        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client_socket.connect((HOST, PORT))
        except Exception as e:
            messagebox.showerror("Error", f"Cannot connect to server: {e}")
            self.root.destroy()
            return

        receive_thread = threading.Thread(target=self.receive_messages)
        receive_thread.daemon = True
        receive_thread.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def display_message(self, message, tag="normal"):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, message + "\n", tag)
        self.chat_area.yview(tk.END)
        self.chat_area.config(state='disabled')

    def receive_messages(self):
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if message == "NICK":
                    self.client_socket.send(self.username.encode('utf-8'))
                elif message:
                    if message.startswith("***") or message.startswith("Welcome"):
                        self.display_message(message, tag="system")
                    elif "[PM from" in message:
                        prefix, hex_payload = message.split(": ", 1)
                        decrypted_text = decrypt_message(hex_payload)
                        self.display_message(f"{prefix}: {decrypted_text}", tag="pm")
                        play_alert_sound()
                    elif "[PM to" in message:
                        prefix, hex_payload = message.split(": ", 1)
                        decrypted_text = decrypt_message(hex_payload)
                        self.display_message(f"{prefix}: {decrypted_text}", tag="pm")
                    else:
                        if ": " in message:
                            sender, hex_payload = message.split(": ", 1)
                            decrypted_text = decrypt_message(hex_payload)
                            self.display_message(f"{sender}: {decrypted_text}", tag="normal")
                        else:
                            self.display_message(message, tag="normal")
                        play_alert_sound()
                else:
                    break
            except:
                break

    def send_message(self, event=None):
        raw_msg = self.msg_entry.get().strip()
        if raw_msg:
            self.msg_entry.delete(0, tk.END)
            try:
                if raw_msg.startswith("/msg "):
                    parts = raw_msg.split(" ", 2)
                    if len(parts) >= 3:
                        target_user = parts[1]
                        private_body = parts[2]
                        encrypted_body = encrypt_message(private_body)
                        wire_payload = f"/msg {target_user} {encrypted_body}"
                        self.client_socket.send(wire_payload.encode('utf-8'))
                    else:
                        self.display_message("*** Usage: /msg <username> <message> ***", tag="system")
                else:
                    encrypted_body = encrypt_message(raw_msg)
                    self.client_socket.send(encrypted_body.encode('utf-8'))
                    self.display_message(f"You: {raw_msg}", tag="self")
            except:
                self.display_message("[ERROR] Failed to send message.", tag="system")

    def on_close(self):
        try:
            self.client_socket.close()
        except:
            pass
        self.root.destroy()

if __name__ == "__main__":
    ChatGUI()