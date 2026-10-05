import socket
import asyncio

HOST = "127.0.0.1"
PORT = 6380

async def redis_client():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        await asyncio.get_event_loop().run_in_executor(None, client.connect, ("127.0.0.1", 6379))

        print("Connected to Mini Redis")
        print("Type commands like:")
        print("SET name Kavan")
        print("GET name")
        print("EXISTS name")
        print("DELETE name")
        print("EXPIRE name 10")
        print("TTL name")
        print("DBSIZE")
        print("PING")
        print("Type EXIT to quit")

        while True:
            command = input("redis> ")

            if command.upper() == "EXIT":
                break

            client.sendall((command + "\r\n").encode())

            response = client.recv(4096)

            if not response:
                break
            print(response.decode().strip())

if __name__ == "__main__":
   try:   
        asyncio.run(redis_client())
   except KeyboardInterrupt:
        print("\nClient exited.")
   except Exception as e:
        print(f"\nAn error occurred: {e}")
   finally:
        print("Client closed.")