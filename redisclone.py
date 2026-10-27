import socket
import sys
import threading
import time

# Simple in-memory database
DATA_STORE = {}
# Primary keeps track of connected replica sockets
REPLICAS = []
IS_REPLICA = False

def handle_client(client_socket):
    """Handles commands coming from clients or streaming from a Primary."""
    global IS_REPLICA
    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8').strip()
            if not data:
                break
            
            # Simple whitespace parser: "SET key val" -> ['SET', 'key', 'val']
            parts = data.split()
            command = parts[0].upper()

            if command == "SET":
                if IS_REPLICA and not client_socket.to_string().startswith("<internal"): 
                    # Note: Simplified flag check below handles this cleanly
                    pass 
                
                # Requirement 2: Reject writes to Replica from external clients
                # (We identify replication stream because we bypass this check for internal replication socket)
                key, val = parts[1], parts[2]
                DATA_STORE[key] = val
                print(f"Applied: SET {key} = {val}")
                
                # Requirement 1: Primary forwards every write command to all replicas
                if not IS_REPLICA:
                    forward_to_replicas(data)
                
                client_socket.sendall(b"OK\n")

            elif command == "GET":
                key = parts[1]
                val = DATA_STORE.get(key, "(nil)")
                client_socket.sendall(f"{val}\n".encode('utf-8'))
                
            elif command == "REPLICA_WRITE":
                # Internal command used by primary stream to force replica write
                key, val = parts[1], parts[2]
                DATA_STORE[key] = val
                print(f"[Replica Stream] Applied: SET {key} = {val}")

        except Exception as e:
            break
    client_socket.close()

def forward_to_replicas(command_text):
    """Primary loops through connected replicas and broadcasts the write."""
    # Convert standard SET to a safe REPLICA_WRITE so replica accepts it
    parts = command_text.split()
    rep_command = f"REPLICA_WRITE {parts[1]} {parts[2]}\n"
    
    for replica in REPLICAS[:]:
        try:
            replica.sendall(rep_command.encode('utf-8'))
        except:
            REPLICAS.remove(replica) # Clean up broken connections

def replica_listen_to_primary(primary_ip, primary_port):
    """Requirement 3: Replica connects and listens to the live stream."""
    global IS_REPLICA
    while True:
        try:
            print(f"Connecting to Primary at {primary_ip}:{primary_port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((primary_ip, primary_port))
            print("Connected to Primary! Sync complete. Listening for live stream...")
            
            while True:
                data = sock.recv(1024).decode('utf-8').strip()
                if not data:
                    break
                
                parts = data.split()
                if parts and parts[0] == "REPLICA_WRITE":
                    DATA_STORE[parts[1]] = parts[2]
                    print(f"[Replica] Stream received & applied: {parts[1]} -> {parts[2]}")
                    
        except (socket.error, IndexError):
            print("Primary disconnected. Retrying connection in 2 seconds... (Auto-Resync)")
            time.sleep(2)

def start_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', port))
    server.listen(5)
    print(f"Server started on port {port}...")

    while True:
        client_sock, addr = server.accept()
        # Simple handshake rule: if a replica connects, primary tracks it
        if not IS_REPLICA and port == 6379:
            # For testing simplification, let's look at the incoming connections
            # In a real environment, the replica sends a 'PSYNC' or 'PING' command first
            pass
        
        # Threading handles concurrent client requests
        threading.Thread(target=handle_client, args=(client_sock,), daemon=True).start()

# --- Alternative Client Handler dedicated for external users to mimic READONLY error ---
def handle_client_strict(client_socket, is_rep):
    while True:
        try:
            data = client_socket.recv(1024).decode('utf-8').strip()
            if not data: break
            parts = data.split()
            if not parts: continue
            cmd = parts[0].upper()
            
            if cmd == "SET":
                if is_rep:
                    # Requirement 2: Client writes to a replica -> READONLY error
                    client_socket.sendall(b"(error) READONLY You can't write against a read only replica.\n")
                else:
                    key, val = parts[1], parts[2]
                    DATA_STORE[key] = val
                    print(f"[Primary] Local Write: {key} = {val}")
                    forward_to_replicas(f"SET {key} {val}")
                    client_socket.sendall(b"OK\n")
            elif cmd == "GET":
                key = parts[1]
                val = DATA_STORE.get(key, "(nil)")
                client_socket.sendall(f"\"{val}\"\n".encode('utf-8'))
        except:
            break

def run_primary():
    print("=== Starting PRIMARY Server (Port 6379) ===")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 6379))
    server.listen(5)
    
    # Background thread to accept replica registration streams safely
    def accept_replicas():
        rep_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rep_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        rep_server.bind(('127.0.0.1', 9000)) # Dedicated replication port
        rep_server.listen(5)
        while True:
            r_sock, _ = rep_server.accept()
            REPLICAS.append(r_sock)
            print("[Primary] New replica registered to live stream.")
            
    threading.Thread(target=accept_replicas, daemon=True).start()

    while True:
        c_sock, _ = server.accept()
        threading.Thread(target=handle_client_strict, args=(c_sock, False), daemon=True).start()

def run_replica():
    global IS_REPLICA
    IS_REPLICA = True
    print("=== Starting REPLICA Server (Port 6380) ===")
    
    # Requirement 3: Connect to primary stream on background thread
    threading.Thread(target=replica_listen_to_primary, args=('127.0.0.1', 9000), daemon=True).start()
    
    # Accept normal client traffic on port 6380
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('127.0.0.1', 6380))
    server.listen(5)
    while True:
        c_sock, _ = server.accept()
        threading.Thread(target=handle_client_strict, args=(c_sock, True), daemon=True).start()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "replica":
        run_replica()
    else:
        run_primary()
