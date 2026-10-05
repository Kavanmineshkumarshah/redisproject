import asyncio

import logging

from config import BUFFER_SIZE,HOST, PORT, EXPIRY_INTERVAL

from protocol import encode_response, parse_command

logger = logging.getLogger(__name__)


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
