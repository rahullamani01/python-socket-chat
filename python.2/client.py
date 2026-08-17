import socket
import threading
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog, scrolledtext

HOST = '127.0.0.1'
PORT = 65433

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
        self.root.title("Python Socket Chat Room")
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
                    if message.startswith("***"):
                        self.display_message(message, tag="system")
                    elif "[PM from" in message or "[PM to" in message:
                        self.display_message(message, tag="pm")
                        play_alert_sound()
                    else:
                        self.display_message(message, tag="normal")
                        play_alert_sound()
                else:
                    break
            except:
                break

    def send_message(self, event=None):
        msg = self.msg_entry.get().strip()
        if msg:
            self.msg_entry.delete(0, tk.END)
            try:
                self.client_socket.send(msg.encode('utf-8'))
                if not msg.startswith("/"):
                    self.display_message(f"You: {msg}", tag="self")
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