import asyncio
import sys
from collections import defaultdict

class RedisConnection:
    """Tracks state and communication for an individual client connection."""
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.subscribed_channels = set()

    @property
    def is_subscribed(self) -> bool:
        return len(self.subscribed_channels) > 0

    async def send_resp_array(self, items: list):
        """Serializes list items into a valid RESP Array (*N\r\n...)."""
        try:
            resp = f"*{len(items)}\r\n"
            for item in items:
                if item is None:
                    resp += "$-1\r\n"
                elif isinstance(item, int):
                    resp += f":{item}\r\n"
                else:
                    s_item = str(item)
                    resp += f"${len(s_item.encode('utf-8'))}\r\n{s_item}\r\n"
            self.writer.write(resp.encode('utf-8'))
            await self.writer.drain()
            return True
        except (ConnectionResetError, BrokenPipeError, OSError):
            return False


class RedisPubSubServer:
    def __init__(self, host="127.0.0.1", port=6381):
        self.host = host
        self.port = port
        # Global maps: channel -> set of RedisConnection objects
        self.channel_subscribers = defaultdict(set)
        self._lock = asyncio.Lock()

    async def start(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"🚀 Redis Pub/Sub Server listening on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = RedisConnection(reader, writer)
        print(f"🔌 New client connection established.")
        try:
            while True:
                # 1. Parse RESP or Inline commands safely
                line = await reader.readline()
                if not line:
                    break

                if line.startswith(b'*'):
                    try:
                        num_elements = int(line[1:].strip())
                        args = []
                        for _ in range(num_elements):
                            await reader.readline()  # Skip size line ($X\r\n)
                            val_line = await reader.readline()
                            if not val_line:
                                break
                            args.append(val_line.strip().decode('utf-8'))
                    except Exception:
                        writer.write(b"-ERR Protocol error\r\n")
                        await writer.drain()
                        continue
                else:
                    # Fallback for plain text inline commands (e.g. telnet / netcat)
                    args = line.strip().decode('utf-8').split()
                
                if not args:
                    continue

                cmd = args[0].upper()

                # 2. State restriction enforcement
                if conn.is_subscribed and cmd not in ("SUBSCRIBE", "UNSUBSCRIBE", "PING", "QUIT"):
                    err_msg = "-ERR only (UN)SUBSCRIBE / PING / QUIT allowed in this state\r\n"
                    writer.write(err_msg.encode('utf-8'))
                    await writer.drain()
                    continue

                # 3. Command Routing
                if cmd == "SUBSCRIBE":
                    if len(args) < 2:
                        writer.write(b"-ERR wrong number of arguments for 'subscribe' command\r\n")
                        await writer.drain()
                        continue
                    
                    channels_to_sub = args[1:]
                    async with self._lock:
                        for channel in channels_to_sub:
                            conn.subscribed_channels.add(channel)
                            self.channel_subscribers[channel].add(conn)
                            # Notify client of each successful channel subscription
                            await conn.send_resp_array(["subscribe", channel, len(conn.subscribed_channels)])

                elif cmd == "UNSUBSCRIBE":
                    async with self._lock:
                        # If no channels are specified, unsubscribe from ALL current channels
                        channels_to_unsub = args[1:] if len(args) > 1 else list(conn.subscribed_channels)
                        
                        # Edge case: If client is not subscribed to anything and types UNSUBSCRIBE
                        if not channels_to_unsub:
                            await conn.send_resp_array(["unsubscribe", None, 0])
                            continue

                        for channel in list(channels_to_unsub):
                            if channel in conn.subscribed_channels:
                                conn.subscribed_channels.remove(channel)
                                self.channel_subscribers[channel].discard(conn)
                                if not self.channel_subscribers[channel]:
                                    del self.channel_subscribers[channel]
                            
                            await conn.send_resp_array(["unsubscribe", channel, len(conn.subscribed_channels)])

                elif cmd == "PUBLISH":
                    if len(args) != 3:
                        writer.write(b"-ERR wrong number of arguments for 'publish' command\r\n")
                        await writer.drain()
                        continue

                    channel, message = args[1], args[2]
                    receivers_count = 0
                    dead_connections = []

                    async with self._lock:
                        subscribers = list(self.channel_subscribers.get(channel, []))
                        
                        # Push ["message", channel, data] to active listeners
                        for sub in subscribers:
                            success = await sub.send_resp_array(["message", channel, message])
                            if success:
                                receivers_count += 1
                            else:
                                dead_connections.append(sub)

                        # FIXED: Removed the nested 'async with self._lock' deadlock bug!
                        if dead_connections:
                            for dead_conn in dead_connections:
                                for ch in list(dead_conn.subscribed_channels):
                                    self.channel_subscribers[ch].discard(dead_conn)
                                    if not self.channel_subscribers[ch]:
                                        del self.channel_subscribers[ch]

                    # PUBLISH returns numeric count of clients that received it
                    writer.write(f":{receivers_count}\r\n".encode('utf-8'))
                    await writer.drain()

                elif cmd == "PING":
                    if conn.is_subscribed:
                        # Standard Redis returns ["pong", ""] array if client is subscribed
                        await conn.send_resp_array(["pong", ""])
                    else:
                        writer.write(b"+PONG\r\n")
                        await writer.drain()

                elif cmd == "QUIT":
                    writer.write(b"+OK\r\n")
                    await writer.drain()
                    break
                else:
                    writer.write(b"-ERR unknown command\r\n")
                    await writer.drain()

        except asyncio.CancelledError:
            pass
        finally:
            # 4. Clean up connection references on disconnect
            async with self._lock:
                for ch in list(conn.subscribed_channels):
                    self.channel_subscribers[ch].discard(conn)
                    if not self.channel_subscribers[ch]:
                        del self.channel_subscribers[ch]
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            print("🔌 Connection dropped safely.")

if __name__ == "__main__":
    server = RedisPubSubServer()
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\nStopping Server...")
