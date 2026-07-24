import socket
import threading

HOST = '127.0.0.1'
PORT = 65433

def handle_client(client_socket, client_address):
    print(f"[NEW CONNECTION] {client_address} connected.")
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break
            print(f"[{client_address}] {message}")
            
            reply = input(f"Type reply to {client_address}: ")
            client_socket.send(reply.encode('utf-8'))
        except:
            break
            
    client_socket.close()
    print(f"[DISCONNECTED] {client_address} disconnected.")

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"[STARTING] Multi-threaded Server is listening on {HOST}:{PORT}...")

while True:
    client_socket, client_address = server_socket.accept()
    thread = threading.Thread(target=handle_client, args=(client_socket, client_address))
    thread.start()
    print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")