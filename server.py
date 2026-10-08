import asyncio

import logging

from config import BUFFER_SIZE,HOST, PORT, EXPIRY_INTERVAL

from protocol import encode_response, parse_command

logger = logging.getLogger(__name__)

data_store = {}  # In-memory key-value store
expiry_store = {} 
def parse_resp_buffer(buffer:bytes)->tuple[list[list[bytes]]] :
    commands=[]
    lines=buffer.split(b'\n')
    idx=0
    while idx<len(lines):
        line=linexes[idx].strip()
        if not line:                  
            idx+=1
            continue
        if line.startswith(b'*'):
            try:
                num_elements=int(line[1:])
            except ValueError:
                raise ValueError("Invalid RESP array length")
            command_tokens=[]
            valid_array=[]
            current_idx=idx+1
            for _ in range(num_elements):
                if current_idx >= len(lines) - 1:
                    valid_array = False
                    break
                    
                bulk_header = lines[current_idx]
                # Bulk strings start with '$'
                if not bulk_header.startswith(b'$'):
                    valid_array = False
                    break
                    
                current_idx += 1
                if current_idx >= len(lines) - 1:
                    valid_array = False
                    break
                    
                actual_data = lines[current_idx]
                command_tokens.append(actual_data)
                current_idx += 1
                
            if valid_array:
                commands.append(command_tokens)
                idx = current_idx  # Move buffer index past this fully parsed command
                continue
        
        idx += 1
        
    # Reconstruct whatever chunk remains unparsed at the very end
    remaining = b'\r\n'.join(lines[idx:])
    return commands, remaining

def is_expired(key: bytes) -> bool:
    """Helper to check if a key has expired. If it has, delete it lazily."""
    if key in expiry_store:
        if time.time() > expiry_store[key]:
            # Key has expired, clean it up (Lazy Deletion)
            data_store.pop(key, None)
            expiry_store.pop(key, None)
            return True
    return False

# ============================================================================
# Task 3 & 4: Command Execution Engine & Error Handling
# ============================================================================
def handle_command(tokens: list[bytes]) -> bytes:
    """Executes a single parsed command and returns a RESP-formatted byte response."""
    if not tokens:
        return b""
        
    command = tokens[0].upper()
    
    try:
        # 1. PING
        if command == b"PING":
            return b"+PONG\r\n"
            
        # 2. SET key value
        elif command == b"SET":
            if len(tokens) < 3:
                return b"-ERR wrong number of arguments for 'set' command\r\n"
            key, value = tokens[1], tokens[2]
            data_store[key] = value
            expiry_store.pop(key, None) # Clear any previous expiration
            return b"+OK\r\n"
            
        # 3. GET key
        elif command == b"GET":
            if len(tokens) < 2:
                return b"-ERR wrong number of arguments for 'get' command\r\n"
            key = tokens[1]
            
            if is_expired(key) or key not in data_store:
                return b"$-1\r\n" # RESP Null Bulk String
                
            value = data_store[key]
            return f"${len(value)}\r\n".encode() + value + b"\r\n"
            
        # 4. DEL key
        elif command == b"DEL":
            if len(tokens) < 2:
                return b"-ERR wrong number of arguments for 'del' command\r\n"
            key = tokens[1]
            
            # Active check if it's expired before evaluating existence
            if is_expired(key):
                return b":0\r\n"
                
            if key in data_store:
                del data_store[key]
                expiry_store.pop(key, None)
                return b":1\r\n" # RESP Integer 1
            return b":0\r\n"     # RESP Integer 0
            
        # 5. EXPIRE key seconds
        elif command == b"EXPIRE":
            if len(tokens) < 3:
                return b"-ERR wrong number of arguments for 'expire' command\r\n"
            key, seconds_bytes = tokens[1], tokens[2]
            
            if is_expired(key) or key not in data_store:
                return b":0\r\n" # Key doesn't exist
                
            try:
                seconds = int(seconds_bytes)
                expiry_store[key] = time.time() + seconds
                return b":1\r\n" # Success
            except ValueError:
                return b"-ERR value is not an integer or out of range\r\n"
                
        # 6. TTL key
        elif command == b"TTL":
            if len(tokens) < 2:
                return b"-ERR wrong number of arguments for 'ttl' command\r\n"
            key = tokens[1]
            
            if is_expired(key) or key not in data_store:
                return b":-2\r\n" # Key does not exist or expired
                
            if key not in expiry_store:
                return b":-1\r\n" # Key exists but has no associated expire
                
            remaining_ttl = int(expiry_store[key] - time.time())
            return f":{remaining_ttl}\r\n".encode()
            
        # Task 4: Catch Unknown Commands Safely
        else:
            return f"-ERR unknown command '{command.decode('utf-8', errors='ignore')}'\r\n".encode()
            
    except Exception as e:
        # Universal fallback catch-all to prevent server crash
        return f"-ERR internal server error: {str(e)}\r\n".encode()

# ============================================================================
# Task 1 & 5: Connection Handling & Pipelining
# ============================================================================
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles an individual TCP client lifecycle and supports request pipelining."""
    client_address = writer.get_extra_info('peername')
    print(f"[+] Client connected from {client_address}")
    
    buffer = b""
    
    try:
        while True:
            # Read chunks up to 4096 bytes from the TCP socket buffer
            data = await reader.read(4096)
            if not data:
                break # Client disconnected closed connection gracefully
                
            buffer += data
            
            # Task 5: Parse ALL complete commands waiting in the aggregate buffer
            commands, buffer = parse_resp_buffer(buffer)
            
            if commands:
                response_payload = b""
                for tokens in commands:
                    # Process commands sequentially in order
                    response_payload += handle_command(tokens)
                    
                # Flush out all collected responses in one atomic network write
                writer.write(response_payload)
                await writer.drain()
                
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[-] Error handling client {client_address}: {e}")
    finally:
        print(f"[-] Client disconnected from {client_address}")
        writer.close()
        await writer.wait_closed()

async def main():
    host = "127.0.0.1"
    port = 6380
    
    # Task 1: Initialize the async TCP Server Loop
    server = await asyncio.start_server(handle_client, host, port)
    print(f"[*] Redis Custom Engine running on {host}:{port}...")
    
    async with server:
        await server.serve_forever()

class RedisServer:
    """Async TCP server for Mini Redis."""

    def __init__(self, command_handler, host=HOST, port=PORT, expiry_interval=EXPIRY_INTERVAL):
        self.command_handler = command_handler
        self.host = host
        self.port = port
        self.expiry_interval = expiry_interval
        self._server = None
        self._expiry_task = None

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        address = writer.get_extra_info("peername")
        logger.info("Client connected: %s", address)
        pending = bytearray()

        try:
            while True:
                data = await reader.read(BUFFER_SIZE)
                if not data:
                    break

                pending.extend(data)
                while b"\n" in pending:
                    line, _, remainder = pending.partition(b"\n")
                    pending = bytearray(remainder)
                    try:
                        request = line.decode("utf-8").rstrip("\r")
                    except UnicodeDecodeError:
                        response = "-ERR invalid input"
                    else:
                        if not request.strip():
                            continue
                        try:
                            response = self.command_handler.execute(parse_command(request))
                        except Exception:
                            logger.exception("Command failed for client %s", address)
                            response = "-ERR internal server error"

                    writer.write(encode_response(response).encode("utf-8"))
                    await writer.drain()
        except (ConnectionError, OSError):
            logger.info("Client disconnected: %s", address)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Client handler failed for %s", address)
            try:
                writer.write(b"-ERR internal server error\r\n")
                await writer.drain()
            except (ConnectionError, OSError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            logger.info("Connection closed: %s", address)

    async def start(self):
        if self._server is not None:
            raise RuntimeError("Server is already running")
        self._server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )
        addresses = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        self._expiry_task = asyncio.create_task(self._expire_loop())
        logger.info("Mini Redis server started on %s", addresses)
        return self._server

    async def _expire_loop(self):
        while True:
            await asyncio.sleep(self.expiry_interval)
            expired_count = self.command_handler.store.expire_keys()
            if expired_count:
                logger.debug("Expired %d keys", expired_count)

    async def close(self):
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._expiry_task is not None:
            self._expiry_task.cancel()
            try:
                await self._expiry_task
            except asyncio.CancelledError:
                pass
            self._expiry_task = None

    async def serve_forever(self):
        server = await self.start()
        try:
            async with server:
                await server.serve_forever()
        finally:
            await self.close()
if __name__ == "__main__":
  try:
    asyncio.run(main())
  except KeyboardInterrupt:
    print("\n[*] Shutting down engine server gracefully.")

