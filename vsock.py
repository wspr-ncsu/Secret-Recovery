import socket, threading, traceback
import enclave.app as enclave
import enclave.attest as attest
import skrecovery.config as config

HEADER = 64
FORMAT = "utf-8"
BUFFER_SIZE = 600 * 1024 * 1024
DISCONNECT_MESSAGE = "<<EOT>>"
SERVER = socket.VMADDR_CID_ANY if config.is_nitro_env() else socket.gethostbyname(socket.gethostname())
SOCK_FAMILY = socket.AF_VSOCK if config.is_nitro_env() else socket.AF_INET
ADDR = (SERVER, config.VSOCK_PORT)

def server_create(address: tuple = None) -> socket.socket:
    server = socket.socket(SOCK_FAMILY, socket.SOCK_STREAM)
    server.bind(address if address else ADDR)
    server.listen()
    return server

def connect(address: tuple = None) -> socket.socket:
    client: socket.socket = socket.socket(SOCK_FAMILY, socket.SOCK_STREAM)
    # client.settimeout(60 * 5)
    client.connect(address if address else ADDR)
    return client

def disconnect(conn: socket.socket):
    send(conn, DISCONNECT_MESSAGE)
    conn.close()

def recv_fixed_msg(conn: socket.socket, msg_length: int):
    msg = ''
    while len(msg) < msg_length:
        num_bytes = min(BUFFER_SIZE, msg_length - len(msg))
        m = conn.recv(num_bytes).decode(FORMAT)
        msg += m
    return msg

def response_recv(conn: socket.socket) -> str:
    data: str = ''
    msg_length = conn.recv(HEADER).decode(FORMAT)
    if msg_length:
        msg_length = int(msg_length)
        data = recv_fixed_msg(conn, msg_length)
    return data

def server_handle_client_connection(conn: socket.socket, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    while True:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            print('Message length: ', msg_length)
            msg = recv_fixed_msg(conn, msg_length)
            
            if msg == DISCONNECT_MESSAGE:
                break
                
            print('Processing request...')
            res: str = enclave.run(req=msg)
            send(conn=conn, msg=res)
            
    conn.close()
    print(f"[CONNECTION CLOSED] {addr} disconnected.")
    
def server_start(server: socket.socket):
    attest.init()
    
    while True:
        conn, addr = server.accept()
        thread = threading.Thread(
            target=server_handle_client_connection, 
            args=(conn, addr)
        )
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")
        
def send(conn: socket.socket, msg: str):
    message = msg.encode(FORMAT)
    msg_length = len(message)
    send_length = str(msg_length).encode(FORMAT)
    send_length += b" " * (HEADER - len(send_length))
    conn.send(send_length)
    conn.sendall(message)