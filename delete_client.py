import asyncio
import socket
import threading

# A thread-safe set or list to keep track of active client sockets
active_clients = set()
# A lock to prevent race conditions when modifying the active_clients set
clients_lock = threading.Lock()

def handle_client(client_socket, client_address):
    """
    Handles the lifecycle of a single connected client.
    """
    print(f"[NEW CONNECTION] {client_address} connected.")
    
    # Add the new client to the active list safely
    with clients_lock:
        active_clients.add(client_socket)

    try:
        while True:
            # Receive data from the client (blocks until data arrives)
            data = client_socket.recv(1024)
            
            # Scenario 1: Clean closure. recv() returns 0 bytes
            if not data:
                print(f"[DISCONNECT] {client_address} closed the connection cleanly.")
                break
                
            # Process the data if the client is still active
            print(f"[{client_address}] sent: {data.decode('utf-8')}")
            
    except (ConnectionResetError, OSError) as e:
        # Scenario 2: Abrupt disconnection (network drop, crash, etc.)
        print(f"[ERROR] Connection lost abruptly with {client_address}: {e}")
        
    finally:
        # Scenario 3: Clean up and delete the client from the server
        remove_client(client_socket, client_address)

def remove_client(client_socket, client_address):
    """
    Safely removes the client from the active pool and closes the socket.
    """
    with clients_lock:
        if client_socket in active_clients:
            active_clients.remove(client_socket)
            
    try:
        # Ensure the socket is fully closed on the server side
        client_socket.close()
    except OSError:
        pass # Already closed
        
    print(f"[CLEANUP] Client {client_address} removed. Active connections: {len(active_clients)}")
