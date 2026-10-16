import json
import os
import time

class MiniRedis:
    def __init__(self, db_file="dump.json", aof_file="appendonlyfile.aof", save_rules=None):
        self.db = {}               # Memory storage: {key: value}
        self.expiries = {}         # Absolute expiry timestamps: {key: timestamp}
        self.db_file = db_file
        self.aof_file = aof_file
        
        # Configuration for auto-saves: list of tuples (seconds, changes_required)
        # Defaults to saving if 5 writes happen within 10 seconds
        self.save_rules = save_rules or [(10, 5)] 
        self.dirty_count = 0       # Writes since last snapshot
        self.last_save_time = time.time()
        
        # Initialize or recover the database
        self.startup()

    def current_aof_position(self):
        """Returns the current byte offset of the AOF file."""
        if not os.path.exists(self.aof_file):
            return 0
        return os.path.getsize(self.aof_file)

    # ==========================================
    # CORE OPERATIONS & WRITE AHEAD LOGGING (AOF)
    # ==========================================
    def set(self, key, value, ttl=None):
        self.db[key] = value
        if ttl:
            self.expiries[key] = time.time() + ttl
        elif key in self.expiries:
            del self.expiries[key]
        
        # Log to AOF immediately
        command = {"op": "SET", "key": key, "val": value, "ttl": ttl}
        self._write_aof(command)
        
        # Increment mutation counter for snapshot tracking
        self.dirty_count += 1
        self._check_auto_save()

    def get(self, key):
        # Handle lazy expiration cleanup
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

    # ==========================================
    # 1 & 2. ATOMIC SNAPSHOTTING (SAVE / AUTO-SAVE)
    # ==========================================
    def save(self):
        """Saves current memory snapshot atomically to a temp file, then swaps it."""
        # Capture absolute state and current log anchor point
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

    # ==========================================
    # 3. STARTUP RECOVERY ENGINE
    # ==========================================
    def startup(self):
        """Loads the snapshot base and fast-forwards through tail AOF logs."""
        aof_pos = 0
        
        # Step 1: Load base snapshot state if present
        if os.path.exists(self.db_file):
            with open(self.db_file, "r") as f:
                snapshot = json.load(f)
                self.db = snapshot["db"]
                self.expiries = snapshot["expiries"]
                aof_pos = snapshot["aof_position"]
            print(f"[*] Base snapshot loaded. Resuming AOF from byte offset: {aof_pos}")
        
        # Step 2: Seek directly to the un-snapshotted AOF log tail
        if os.path.exists(self.aof_file) and os.path.getsize(self.aof_file) > aof_pos:
            with open(self.aof_file, "r") as f:
                f.seek(aof_pos)  # Skip already-snapshotted commands
                for line in f:
                    if not line.strip(): 
                        continue
                    cmd = json.loads(line)
                    # Replay changes into memory
                    if cmd["op"] == "SET":
                        self.db[cmd["key"]] = cmd["val"]
                        if cmd["ttl"]:
                            self.expiries[cmd["key"]] = cmd["ttl"]
            print("[*] AOF tail replayed successfully.")
        else:
            print("[*] No pending AOF tail changes to replay.")

    # ==========================================
    # 4. BGREWRITEAOF LOG COMPACTION
    # ==========================================
    def bgrewriteaof(self):
        """Rebuilds AOF file directly from memory state to eliminate stale historic mutations."""
        temp_aof = f"{self.aof_file}.tmp"
        
        # Re-serialize what is alive in memory right now into 1 command per key
        with open(temp_aof, "w") as f:
            for key, val in self.db.items():
                # Skip expired keys entirely
                if key in self.expiries and time.time() > self.expiries[key]:
                    continue
                
                ttl = None
                if key in self.expiries:
                    # Calculate remaining relative TTL from absolute snapshot time
                    ttl = max(0, self.expiries[key] - time.time())
                
                cmd = {"op": "SET", "key": key, "val": val, "ttl": ttl}
                f.write(json.dumps(cmd) + "\n")
            f.flush()
            os.fsync(f.fileno())

        # Safely capture the exact snapshot configuration matching this new compacted file
        self.save() 
        
        # Atomic switch: The old long file is discarded for the new concise one
        os.replace(temp_aof, self.aof_file)
        print("[*] AOF log compaction completed.")

    # ==========================================
    # USER INPUT COMMAND LINE INTERFACE (CLI)
    # ==========================================
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
    # Initialize engine (loads existing snapshot and replays outstanding AOF items automatically)
    server = MiniRedis()
    
    # Launch interactive input handler
    server.run_cli()
