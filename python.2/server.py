import socket
import threading
import json
import os
from datetime import datetime

HOST = '127.0.0.1'
PORT = 65433

LOG_FILE = "chat_history.json"
clients = {}

def log_message(sender, recipient, content, msg_type="broadcast"):
    log_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sender": sender,
        "recipient": recipient,
        "type": msg_type,
        "content": content
    }
    
    history = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                history = json.load(f)
        except:
            history = []
            
    history.append(log_entry)
    
    with open(LOG_FILE, "w") as f:
        json.dump(history, f, indent=4)

def broadcast(message, sender_socket=None):
    for client in list(clients.keys()):
        if client != sender_socket:
            try:
                client.send(message.encode('utf-8'))
            except:
                remove_client(client)

def remove_client(client_socket):
    if client_socket in clients:
        username = clients[client_socket]
        del clients[client_socket]
        client_socket.close()
        broadcast(f"*** {username} has left the chat. ***")

def handle_client(client_socket, client_address):
    try:
        client_socket.send("NICK".encode('utf-8'))
        username = client_socket.recv(1024).decode('utf-8').strip()
        
        if not username:
            client_socket.close()
            return

        clients[client_socket] = username
        print(f"[REGISTERED] {client_address} registered as '{username}'")
        
        broadcast(f"*** {username} joined the chat! ***")
        client_socket.send(f"Welcome, {username}! Use /msg <user> <message> for PMs.".encode('utf-8'))

        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
                
            if message.startswith("/msg "):
                parts = message.split(" ", 2)
                if len(parts) >= 3:
                    target_user = parts[1]
                    private_msg = parts[2]
                    
                    target_socket = None
                    for sock, name in clients.items():
                        if name == target_user:
                            target_socket = sock
                            break
                    
                    if target_socket:
                        target_socket.send(f"[PM from {username}]: {private_msg}".encode('utf-8'))
                        client_socket.send(f"[PM to {target_user}]: {private_msg}".encode('utf-8'))
                        log_message(username, target_user, private_msg, msg_type="private")
                    else:
                        client_socket.send(f"*** User '{target_user}' not found. ***".encode('utf-8'))
                else:
                    client_socket.send("*** Usage: /msg <username> <message> ***".encode('utf-8'))
            else:
                formatted_msg = f"{username}: {message}"
                broadcast(formatted_msg, client_socket)
                log_message(username, "ALL", message, msg_type="broadcast")

    except:
        pass
    finally:
        remove_client(client_socket)

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

print(f"[SERVER RUNNING] Listening on {HOST}:{PORT}...")

while True:
    client_socket, client_address = server_socket.accept()
    thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
    thread.start()