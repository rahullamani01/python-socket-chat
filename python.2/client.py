import socket

HOST = '127.0.0.1'
PORT = 65433

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

print(f"[CONNECTING] Trying to connect to server at {HOST}:{PORT}...")
client_socket.connect((HOST, PORT))
print("[CONNECTED] Successfully connected!")

text_to_send = "Hello Server, I've arrived!"
client_socket.send(text_to_send.encode('utf-8'))

server_reply = client_socket.recv(1024).decode('utf-8')
print(f"[SERVER REPLY] {server_reply}")

client_socket.close()
print("[DISCONNECTED] Connection closed.")