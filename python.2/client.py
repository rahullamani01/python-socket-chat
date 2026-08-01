import socket
import threading

HOST = '127.0.0.1'
PORT = 65433

def receive_messages(client_socket):
    while True:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                print("\n[DISCONNECTED] Server closed the connection.")
                break
            print(f"\n{message}")
        except:
            print("\n[ERROR] Lost connection to the server.")
            break

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

try:
    print(f"[CONNECTING] Connecting to server at {HOST}:{PORT}...")
    client_socket.connect((HOST, PORT))
    print("[CONNECTED] Successfully connected to the server!")
    
    receive_thread = threading.Thread(target=receive_messages, args=(client_socket,))
    receive_thread.daemon = True
    receive_thread.start()

    print("Type your messages below (type 'exit' to quit):\n")
    while True:
        msg = input()
        if msg.lower() == 'exit':
            break
        if msg:
            client_socket.send(msg.encode('utf-8'))

except Exception as e:
    print(f"[ERROR] Could not connect: {e}")

finally:
    client_socket.close()
    print("[DISCONNECTED] Client closed.")