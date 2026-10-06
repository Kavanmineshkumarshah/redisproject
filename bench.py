import socket
import time

# Configuration
HOST = '127.0.0.1'
PORT = 6379
COUNT = 1000

def run_sequential_test():
    """Task 1: Send 1,000 commands one by one, waiting for each response."""
    # Connect to the server
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    
    start_time = time.time()
    
    for i in range(COUNT):
        # Construct a simple RESP SET command or plain text depending on your server design
        # Assuming plain text format 'SET key value\r\n' for simplicity
        cmd = f"SET key_{i} value_{i}\r\n".encode()
        client.sendall(cmd)
        
        # We must read and wait for the +OK\r\n response before moving to the next loop iteration
        response = client.recv(1024) 
        
    end_time = time.time()
    client.close()
    
    return end_time - start_time

def run_pipelined_test():
    """Task 2: Jam 1,000 commands together and send them in one giant blast."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((HOST, PORT))
    
    start_time = time.time()
    
    # Construct one massive byte string containing 1,000 commands
    pipeline_buffer = bytearray()
    for i in range(COUNT):
        pipeline_buffer.extend(f"SET key_{i} value_{i}\r\n".encode())
        
    # Send the entire massive byte string in one go
    client.sendall(pipeline_buffer)
    
    # Read the responses back until we have received all 1,000 responses
    # Note: Because TCP is a stream, we might need multiple recvs to get everything.
    bytes_received = 0
    expected_response_len = len(b"+OK\r\n") * COUNT
    
    while bytes_received < expected_response_len:
        data = client.recv(4096)
        if not data:
            break
        bytes_received += len(data)
        
    end_time = time.time()
    client.close()
    
    return end_time - start_time

if __name__ == "__main__":
    print("Starting Benchmark...")
    print("Make sure your server is running before executing this script.\n")
    
    # Task 1
    print("Running Sequential Test...")
    seq_duration = run_sequential_test()
    print(f"Sequential Test Finished.")
    
    # Task 2
    print("Running Pipelined Test...")
    pipe_duration = run_pipelined_test()
    print(f"Pipelined Test Finished.\n")
    
    # Task 3: Comparison
    print("=" * 40)
    print("BENCHMARK RESULTS")
    print("=" * 40)
    print(f"Sequential Time : {seq_duration:.5f} seconds")
    print(f"Pipelined Time  : {pipe_duration:.5f} seconds")
    
    if pipe_duration > 0:
        speedup = seq_duration / pipe_duration
        print(f"Pipelined test was {speedup:.1f}x faster!")
    print("=" * 40)
