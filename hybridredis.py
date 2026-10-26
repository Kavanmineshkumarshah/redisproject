import json
import os
import time

class MiniRedis:
    def __init__(self, db_file="dump.json", aof_file="appendonlyfile.aof", save_rules=None):
        self.db = {}             
        self.expiries = {}       
        self.db_file = db_file
        self.aof_file = aof_file
        self.save_rules = save_rules or [(10, 5)]
        self.dirty_count = 0     
        self.last_save_time = time.time()
        self.startup()

    def current_aof_position(self):
        """Returns the current byte offset of the AOF file."""
        if not os.path.exists(self.aof_file):
            return 0
        return os.path.getsize(self.aof_file)

    def set(self, key, value, ttl=None):
        self.db[key] = value
        if ttl:
            self.expiries[key] = time.time() + ttl
        elif key in self.expiries:
            del self.expiries[key]
            
        command = {"op": "SET", "key": key, "val": value, "ttl": ttl}
        self._write_aof(command)
        self.dirty_count += 1
        self._check_auto_save()

    def get(self, key):
        if key in self.expiries and time.time() > self.expiries[key]:
            del self.db[key]
            del self.expiries[key]
            
        return self.db.get(key, None)

    def _write_aof(self, command):
        """Appends a write command as a single line JSON entry."""
        with open(self.aof_file, "a") as f:
            f.write(json.dumps(command) + "\n")
            f.flush()
            os.fsync(f.fileno())  # Guarantee physical disk write

    def save(self):
        """Saves current memory snapshot atomically to a temp file, then swaps it."""
        snapshot = {
            "aof_position": self.current_aof_position(),
            "db": self.db,
            "expiries": self.expiries
        }
        temp_file = f"{self.db_file}.tmp"
        with open(temp_file, "w") as f:
            json.dump(snapshot, f)
            f.flush()
            os.fsync(f.fileno())  # Flush hardware buffers
            
        # Atomic rename prevents corruption if the process crashes mid-save
        os.replace(temp_file, self.db_file)
        
        # Reset tracking stats
        self.dirty_count = 0
        self.last_save_time = time.time()
        print(f"\n[*] Snapshot saved at AOF byte position: {snapshot['aof_position']}")

    def _check_auto_save(self):
        """Triggers a snapshot if any (Seconds, Writes) threshold is crossed."""
        elapsed = time.time() - self.last_save_time
        for sec, writes in self.save_rules:
            if elapsed >= sec and self.dirty_count >= writes:
                print(f"\n[!] Auto-save triggered: {self.dirty_count} writes in {elapsed:.1f}s")
                self.save()
                break
    def startup(self):
    # ... your existing setup code (opening the file) ...
    
    # Example adjustment inside your file opening logic:
        filepath = "your_snapshot_file.json" # Replace with your actual variable/path
    
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        # If file doesn't exist or is empty, initialize with empty data
           self.data = {} 
        else:
             try:
                with open(filepath, 'r') as f:
                     self.data = json.load(f)
             except json.JSONDecodeError:
              # Fallback if the file gets corrupted
                print("Warning: Snapshot file was corrupted or empty. Initializing empty database.")
                self.data = {}


    def run_cli(self):
        """Starts an interactive CLI loop to take real-time user inputs."""
        print("\n=== MiniRedis Interactive CLI Ready ===")
        print("Commands: SET key val [ttl_seconds] | GET key | SAVE | BGREWRITEAOF | EXIT\n")
        
        while True:
            try:
                user_input = input("miniredis> ").strip()
                if not user_input:
                    continue
                    
                parts = user_input.split()
                cmd = parts[0].upper()
                
                if cmd == "EXIT":
                    print("Shutting down database engine safely...")
                    break
                    
                elif cmd == "SET":
                    if len(parts) < 3:
                        print("(error) ERR wrong number of arguments for 'set' command")
                        continue
                    key = parts[1]
                    val = parts[2]
                    ttl = int(parts[3]) if len(parts) > 3 else None
                    self.set(key, val, ttl)
                    print("OK")
                    
                elif cmd == "GET":
                    if len(parts) != 2:
                        print("(error) ERR wrong number of arguments for 'get' command")
                        continue
                    key = parts[1]
                    res = self.get(key)
                    if res is None:
                        print("(nil)")
                    else:
                        print(f'"{res}"')
                        
                elif cmd == "SAVE":
                    self.save()
                    print("OK")
                    
                elif cmd == "BGREWRITEAOF":
                    self.bgrewriteaof()
                    print("OK")
                    
                else:
                    print(f"(error) ERR unknown command '{cmd}'")
                    
            except ValueError:
                print("(error) ERR value is not an integer or invalid syntax")
            except KeyboardInterrupt:
                print("\nShutting down database engine safely...")
                break

if __name__ == "__main__":
    server = MiniRedis()
    server.run_cli()
