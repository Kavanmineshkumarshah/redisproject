import socket


client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect(("127.0.0.1", 8888))

print("Connected to Mini Redis on 127.0.0.1:8888")
print("Type commands. Type EXIT to quit.")


while True:

    command = input("redis > ")

    if command.upper() == "EXIT":
        break

    if command.strip() == "":
        continue

    client.sendall((command + "\n").encode())

    response = client.recv(1024).decode()

    print(response.strip())


client.close()