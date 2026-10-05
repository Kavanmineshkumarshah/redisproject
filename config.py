import argparse
HOST = "127.0.0.1"
PORT = 6380
BUFFER_SIZE = 4096
EXPIRY_INTERVAL = 10  # seconds
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the Mini Redis server")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
     "--log-level",
    choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    default="INFO",
)
    return parser.parse_args(argv)
