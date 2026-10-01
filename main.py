import asyncio

from store import Store
from commands import CommandHandler
from server import RedisServer


def main():
    store = Store()

    command_handler = CommandHandler(store)

    server = RedisServer(command_handler)

    asyncio.run(server.start())


if __name__ == "__main__":
    main()