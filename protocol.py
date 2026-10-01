import asyncio
import socket
import sys
import time

def parse_command(data: str) -> list[str]:
    """
    Convert input string into command parts.

    Example:
        SET foo bar

    becomes:
        ["SET", "foo", "bar"]
    """

    return data.strip().split()


def encode_response(response) -> str:
    """
    Convert Python response to a Redis-like response.
    """

    if response is None:
        return "(nil)\r\n"

    if response == "OK":
        return "+OK\r\n"

    if isinstance(response, int):
        return f":{response}\r\n"

    if isinstance(response, str):
        if response.startswith("-ERR"):
            return f"{response}\r\n"

        return f"${len(response)}\r\n{response}\r\n"

    return f"${len(str(response))}\r\n{response}\r\n"
def tcp_client(host: str, port: int, command: str) -> str:
    """
    Send a command to the Redis server and return the response.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.connect((host, port))
        client.sendall((command + "\r\n").encode())
        response = client.recv(4096)

    return response.decode().strip()