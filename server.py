import asyncio

import time

data = {}
expiry = {}

def check_expired(key):
    """Remove key if its expiration time has passed."""

    if key in expiry:
        if time.time() >= expiry[key]:
            data.pop(key, None)
            expiry.pop(key, None)
            return True

    return False


async def handle_client(reader, writer):

    print("Client connected")

    while True:

        message = await reader.readline()

        if not message:
            break

        command = message.decode().strip().split()

        if not command:
            continue

        cmd = command[0].upper()

        # ---------------- SET ----------------
        if cmd == "SET":

            if len(command) != 3:
                response = "ERROR: SET key value\n"

            else:
                key = command[1]
                value = command[2]

                data[key] = value

                # SET removes previous expiration
                expiry.pop(key, None)

                response = "OK\n"

        # ---------------- GET ----------------
        elif cmd == "GET":

            if len(command) != 2:
                response = "ERROR: GET key\n"

            else:
                key = command[1]

                check_expired(key)

                if key in data:
                    response = data[key] + "\n"
                else:
                    response = "nil\n"

        # ---------------- EXISTS ----------------
        elif cmd == "EXISTS":

            if len(command) != 2:
                response = "ERROR: EXISTS key\n"

            else:
                key = command[1]

                check_expired(key)

                if key in data:
                    response = "1\n"
                else:
                    response = "0\n"

        # ---------------- DEL ----------------
        elif cmd == "DEL":

            if len(command) != 2:
                response = "ERROR: DEL key\n"

            else:
                key = command[1]

                check_expired(key)

                if key in data:
                    del data[key]
                    expiry.pop(key, None)
                    response = "1\n"
                else:
                    response = "0\n"

        # ---------------- EXPIRE ----------------
        elif cmd == "EXPIRE":

            if len(command) != 3:
                response = "ERROR: EXPIRE key seconds\n"

            else:
                key = command[1]

                try:
                    seconds = int(command[2])
                except ValueError:
                    response = "ERROR: seconds must be integer\n"

                else:
                    check_expired(key)

                    if key not in data:
                        response = "0\n"
                    else:
                        expiry[key] = time.time() + seconds
                        response = "1\n"

        # ---------------- TTL ----------------
        elif cmd == "TTL":

            if len(command) != 2:
                response = "ERROR: TTL key\n"

            else:
                key = command[1]

                check_expired(key)

                if key not in data:
                    response = "-2\n"

                elif key not in expiry:
                    response = "-1\n"

                else:
                    remaining = int(expiry[key] - time.time())

                    if remaining < 0:
                        data.pop(key, None)
                        expiry.pop(key, None)
                        response = "-2\n"
                    else:
                        response = str(remaining) + "\n"
        elif cmd == "PING":
            response = "PONG\n"

        # ---------------- UNKNOWN ----------------
        else:
            response = "ERROR: unknown command\n"

        writer.write(response.encode())
        await writer.drain()

    writer.close()
    await writer.wait_closed()

    print("Client disconnected")


async def main():

    server = await asyncio.start_server(
        handle_client,
        "127.0.0.1",
        8888
    )

    print("Redis server started on 127.0.0.1:8888")

    async with server:
        await server.serve_forever()


asyncio.run(main())




