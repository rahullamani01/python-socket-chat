import socket
import threading

HOST = '127.0.0.1'
PORT = 65433

clients = []

def broadcast(message, sender_socket):
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message)
            except:
                client.close()
                if client in clients:
                    clients.remove(client)

def handle_client(client_socket, client_address):
    print(f"[NEW CONNECTION] {client_address} connected.")
    clients.append(client_socket)
    
    join_msg = f"User {client_address[1]} joined the chat!".encode('utf-8')
    broadcast(join_msg, client_socket)

    while True:
        try:
            message = client_socket.recv(1024)
            if not message:
                break
                
            formatted_msg = f"User {client_address[1]}: {message.decode('utf-8')}".encode('utf-8')
            broadcast(formatted_msg, client_socket)
            
        except:
            break
            
    if client_socket in clients:
        clients.remove(client_socket)
    client_socket.close()
    
    leave_msg = f"User {client_address[1]} left the chat.".encode('utf-8')
    broadcast(leave_msg, client_socket)
    print(f"[DISCONNECTED] {client_address} disconnected.")

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

print(f"[STARTING] Broadcast Server running on {HOST}:{PORT}...")

while True:
    client_socket, client_address = server_socket.accept()
    thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
    thread.start()