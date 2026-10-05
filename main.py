import asyncio
import logging

from store import Store
from commands import CommandHandler
from server import RedisServer
from config import parse_args


def main():
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    store = Store()
    command_handler = CommandHandler(store)
    server = RedisServer(command_handler, host=args.host, port=args.port)
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Server stopped")


if __name__ == "__main__":
    main()