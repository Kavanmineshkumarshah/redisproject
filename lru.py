from collections import OrderedDict


class LRUCache:
    def __init__(self, maxmemory: int):
        """
        Initializes the cache with a specific item capacity (maxmemory).
        """
        self.cache = OrderedDict()
        self.maxmemory = maxmemory

    def get(self, key: str):
        """
        Retrieves a key. If it exists, marks it as Most Recently Used.
        """
        if key not in self.cache:
            return None
        
        self.cache.move_to_end(key)
        return self.cache[key]

    def set(self, key: str, value: str):
        """
        Inserts or updates a key. Evicts the Least Recently Used item 
        (from the front) if the cache exceeds maxmemory.
        """
        if key in self.cache:
            self.cache[key] = value
            self.cache.move_to_end(key)
            return

        if len(self.cache) >= self.maxmemory:
            evicted_key, _ = self.cache.popitem(last=False)
            print(f"⚠️ Cache Full! Evicted oldest key: '{evicted_key}'")

        self.cache[key] = value

    def display(self):
        """Prints the current state of the cache from oldest to newest."""
        if not self.cache:
            print("Cache is empty.")
            return
        
        print("\n--- Current Cache State (Oldest -> Newest) ---")
        for k, v in self.cache.items():
            print(f"[{k}: {v}]", end=" -> ")
        print("END\n")


def main():
    print("=== Interactive LRU Cache ===")
    try:
        cap = int(input("Enter maximum cache capacity (maxmemory): "))
    except ValueError:
        print("Invalid number. Defaulting capacity to 3.")
        cap = 3

    cache = LRUCache(maxmemory=cap)
    print(f"\nCache initialized with capacity = {cap}.")
    print("Commands: set <key> <value> | get <key> | status | exit")

    while True:
        user_input = input("\n> ").strip().split()
        if not user_input:
            continue
            
        command = user_input[0].lower()

        if command == "set" and len(user_input) == 3:
            _, key, val = user_input
            cache.set(key, val)
            print(f"Set {key} = {val}")
        elif command == "get" and len(user_input) == 2:
            _, key = user_input
            val = cache.get(key)
            if val is not None:
                print(f"Found: {key} = {val} (Moved to Most Recently Used)")
            else:
                print(f"Key '{key}' not found.")
        elif command == "status":
            cache.display()
        elif command == "exit":
            print("Exiting...")
            break
        else:
            print("Unknown or incomplete command. Try: 'set a 1', 'get a', 'status', or 'exit'")

if __name__ == "__main__":
    main()
