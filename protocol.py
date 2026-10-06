import asyncio
import socket
import sys
import time
def serialize(data) -> bytes:
    """
    Serialize data to bytes for sending over the network.
    """
    if data is None:
        return b"(nil)"
    if isinstance(data, str):
        return data.encode()

    if isinstance(data, int):
        return str(data).encode()
    if isinstance(data, bytes):
        return data
    if isinstance(data, list):
        return b"\n".join(serialize(item) for item in data)
    if isinstance(data, dict):
        return b"\n".join(
            serialize(key) + b" " + serialize(value) for key, value in data.items()
        )

    raise ValueError("Unsupported data type for serialization")

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
class RESPparser:
    def __init__(self, reader: asyncio.StreamReader):
        self.reader=reader
async def deserialize(reader: asyncio.StreamReader) -> str:
    """
    Deserialize a Redis-like response from the server.
    """

    line = await reader.readline()
    if not line:
        raise ConnectionError("Connection closed by server")

    type_byte = line[0:1]
    payload = line[1:-2]  # Exclude the type byte and CRLF
    if type_byte == b"+":
        return line[1:-2].decode()  # Simple string
    elif type_byte == b"-":
        return line[1:-2].decode()  # Error
    elif type_byte == b":":
        return int(line[1:-2])  # Integer
    elif type_byte == b"$":
        length = int(line[1:-2])
        if length == -1:
            return None  # Null bulk string
        data = await reader.readexactly(length + 2)
        return data[:-2].decode()  # Bulk string
    elif type_byte == b"*":
        count = int(line[1:-2])
        if count == -1:
            return None  # Null array
        items = []
        for _ in range(count):
            items.append(await deserialize(reader))
        return items  # Array
    else:
        raise ValueError("Invalid RESP format")
