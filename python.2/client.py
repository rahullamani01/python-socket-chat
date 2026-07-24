import socket

HOST = '127.0.0.1'
PORT = 65433

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server_socket.bind((HOST, PORT))
server_socket.listen()
print(f"[STARTING] Server is listening on {HOST}:{PORT}...")

client_socket, client_address = server_socket.accept()
print(f"[NEW CONNECTION] Connected to client at {client_address}")

message = client_socket.recv(1024).decode('utf-8')
print(f"[RECEIVED] Client says: {message}")

reply = "Message received loud and clear!"
client_socket.send(reply.encode('utf-8'))

client_socket.close()
server_socket.close()
print("[SHUTDOWN] Server closed.")