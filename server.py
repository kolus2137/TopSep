import socket
import threading

HOST = "0.0.0.0"
PORT = 5555

clients = []


def handle_client(conn, addr):
    print(f"[+] RELAY_NODE CONNECTED: {addr[0]}:{addr[1]}")
    clients.append(conn)

    while True:
        try:
            data = conn.recv(4096)
            if not data:
                break
            for client in clients:
                if client != conn:
                    try:
                        client.send(data)
                    except:
                        if client in clients:
                            clients.remove(client)
        except:
            break

    print(f"[-] RELAY_NODE DISCONNECTED: {addr[0]}:{addr[1]}")
    if conn in clients:
        clients.remove(conn)
    conn.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[ TOPSEP CORE SERVER // LISTENING ON PORT {PORT} ]")

    while True:
        conn, addr = server.accept()
        threading.Thread(
            target=handle_client, args=(conn, addr), daemon=True
        ).start()


if __name__ == "__main__":
    main()