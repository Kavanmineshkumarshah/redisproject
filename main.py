import os
import sys
import time
from database import MicroRedis

def run_automated_diagnostics():
    """Runs a quick pre-flight integrity check on storage rules."""
    print("=== RUNNING ENGINE INTEGRITY DIAGNOSTICS ===")
    for target in ["dump.rdb", "appendonly.aof", "appendonly.aof.tmp"]:
        if os.path.exists(target): os.remove(target)
        
    diag_store = MicroRedis(maxmemory=3, fsync="always")
    diag_store.set("test_key", "diagnostic_passed")
    diag_store.push("test_list", "item_A", "right")
    diag_store.push("test_list", "item_B", "right")
    print(f"LRU Set Verification: {diag_store.get('test_key')}")
    print(f"List Verification:\n{diag_store.lrange('test_list', 0, -1)}")
    diag_store.aof.close()
    print("============================================\n")

def start_interactive_cli():
    """Launches an interactive prompt accepting customizable user inputs directly."""
    # Memory threshold configured to 5 for standard user CLI interactions
    store = MicroRedis(maxmemory=5, fsync="everysec")
    
    print("Welcome to MicroRedis CLI implementation!")
    print("Available Commands:")
    print("  - Strings: SET <key> <val> [EX <seconds>], GET <key>")
    print("  - Deques:  LPUSH <key> <val>, RPUSH <key> <val>, LPOP <key>, RPOP <key>")
    print("  - Lists:   LRANGE <key> <start> <stop>, TYPE <key>")
    print("  - Engine:  SAVE, REWRITE, EXIT\n")

    while True:
        try:
            user_input = input("micro-redis> ").strip()
            if not user_input:
                continue
                
            # Simple space splitting that honors double-quoted strings
            parts = []
            current = []
            in_quotes = False
            for char in user_input:
                if char == '"':
                    in_quotes = not in_quotes
                elif char == ' ' and not in_quotes:
                    if current:
                        parts.append("".join(current))
                        current = []
                else:
                    current.append(char)
            if current:
                parts.append("".join(current))

            cmd = parts[0].upper()
            
            if cmd == "EXIT":
                print("Shutting down core engines...")
                store.aof.close()
                break

            elif cmd == "SET":
                if len(parts) < 3:
                    print("(error) ERR wrong number of arguments for 'set' command")
                    continue
                key, val = parts[1], parts[2]
                ex = None
                if len(parts) >= 5 and parts[3].upper() == "EX":
                    try:
                        ex = int(parts[4])
                    except ValueError:
                        print("(error) ERR value is not an integer or out of range")
                        continue
                print(store.set(key, val, ex))

            elif cmd == "GET":
                if len(parts) < 2:
                    print("(error) ERR wrong number of arguments for 'get' command")
                    continue
                res = store.get(parts[1])
                print(res if res is not None else "(nil)")

            elif cmd == "LPUSH":
                if len(parts) < 3:
                    print("(error) ERR wrong number of arguments for 'lpush' command")
                    continue
                print(store.push(parts[1], parts[2], side="left"))

            elif cmd == "RPUSH":
                if len(parts) < 3:
                    print("(error) ERR wrong number of arguments for 'rpush' command")
                    continue
                print(store.push(parts[1], parts[2], side="right"))

            elif cmd == "LPOP":
                if len(parts) < 2:
                    print("(error) ERR wrong number of arguments for 'lpop' command")
                    continue
                print(store.pop(parts[1], side="left"))

            elif cmd == "RPOP":
                if len(parts) < 2:
                    print("(error) ERR wrong number of arguments for 'rpop' command")
                    continue
                print(store.pop(parts[1], side="right"))

            elif cmd == "LRANGE":
                if len(parts) < 4:
                    print("(error) ERR wrong number of arguments for 'lrange' command")
                    continue
                try:
                    start, stop = int(parts[2]), int(parts[3])
                except ValueError:
                    print("(error) ERR value is not an integer or out of range")
                    continue
                print(store.lrange(parts[1], start, stop))

            elif cmd == "TYPE":
                if len(parts) < 2:
                    print("(error) ERR wrong number of arguments for 'type' command")
                    continue
                print(store.type(parts[1]))

            elif cmd == "SAVE":
                print(store.save_snapshot())

            elif cmd == "REWRITE":
                print(store.rewrite_aof())

            else:
                print(f"(error) ERR unknown command `{parts[0]}`")

        except KeyboardInterrupt:
            print("\nUse 'EXIT' or Ctrl+D to leave the program shell.")
        except Exception as e:
            print(f"(error) Internal processing failure: {e}")

if __name__ == "__main__":
    # If users provide parameters, jump past checks directly to interaction loops
    if len(sys.argv) > 1 and sys.argv[1] == "--cli-only":
        start_interactive_cli()
    else:
        run_automated_diagnostics()
        start_interactive_cli()

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
