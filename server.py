import asyncio



class RedisServer:
    """Async TCP server for Mini Redis."""


    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        address = writer.get_extra_info("peername")

        print(f"Client connected: {address}")

        try:
            while True:
                data = await reader.read(BUFFER_SIZE)

                if not data:
                    break

                request = data.decode()

                # Support multiple commands separated by lines.
                for line in request.splitlines():

                    if not line.strip():
                        continue

                    command = parse_command(line)

                    response = self.command_handler.execute(command)

                    encoded = encode_response(response)

                    writer.write(encoded.encode())

                    await writer.drain()

        except ConnectionResetError:
            print(f"Client disconnected: {address}")

        finally:
            writer.close()
            await writer.wait_closed()

            print(f"Connection closed: {address}")

    async def start(self):
        server = await asyncio.start_server(
            self.handle_client,
            HOST,
            PORT,
        )

        addresses = ", ".join(
            str(sock.getsockname())
            for sock in server.sockets
        )

        print(f"Mini Redis server started on {addresses}")

        async with server:
            await server.serve_forever()
