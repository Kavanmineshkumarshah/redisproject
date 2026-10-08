import os
import time
import threading
import asyncio

def encode_resp(*args) -> bytes:
    """
    Encode a command and its arguments into the RESP format.
    """
    resp = f"*{len(args)}\r\n"
    for arg in args:
        if isinstance(arg, str):
            arg = arg.encode()
        resp += f"${len(arg)}\r\n".encode() + arg + b"\r\n"
    return resp.encode()
class AOFwriter:
    def __init__(self, filename: str):
        self.filename = filename
        self.lock = threading.Lock()
        self.file = open(self.filename, 'ab')  # Open in append binary mode
        self.stop_event = threading.Event()
        self.policy = policy
        if self.policy == "everysec":
            self.flush_thread = threading.Thread(target=self.flush_periodically)
            self.flush_thread.start()
    def write_command(self, *args):
        """Append a command to the AOF log using the configured fsync policy."""
        data = encode_resp(*args)
        with self.lock:
            self.file.write(data)
            if self.policy == "always":
                self.file.flush()
                os.fsync(self.file.fileno())
            elif self.policy == "no":
                pass # Rely on OS kernel buffer

    def _background_fsync(self):
        """Background thread for the 'everysec' policy."""
        while not self.stop_event.is_set():
            time.sleep(1)
            with self.lock:
                self.file.flush()
                os.fsync(self.file.fileno())

    def close(self):
        """Gracefully close and sync the AOF file."""
        self.stop_event.set()
        if self.policy == "everysec":
            self.bg_thread.join()
        with self.lock:
            self.file.flush()
            os.fsync(self.file.fileno())
            self.file.close()
        
    def write(self, command: bytes):
        with self.lock:
            self.file.write(command)
            self.file.flush()  # Ensure it's written to disk

    def close(self):
        with self.lock:
            self.file.close()  
"""This breakdown explains each requirement step-by-step, mimicking how production-grade data stores like Redis handle memory limits, durability, performance optimization, and advanced data types. ------------------------------ ## Part 1: Advanced Features (Items 3–6)## 3. Eviction Policy (LRU) with a Memory Cap * What: Set a maximum threshold (maxmemory) for how many keys your store can hold. Once full, the store automatically drops the Least Recently Used (LRU) key to make space for new data. * How: Use Python's built-in collections.OrderedDict. * Every time a key is accessed or updated (GET or SET), call my_dict.move_to_end(key). This shifts it to the back, marking it as "most recently used." * If len(my_dict) > maxmemory, execute my_dict.popitem(last=False). This removes the item at the front (the oldest, least recently used item). * Why: Caches have finite RAM. If they grow unchecked, the system will run out of memory and crash. * Done when: If your cap is 3 keys and you write A, B, C, then read A (making A fresh), and then write D, key B is evicted because it was left untouched. ## 4. Snapshotting (RDB-style) alongside the AOF * What: Instead of relying entirely on an Append-Only Log (AOF) that tracks every single historical change, you periodically save a complete, point-in-time point-in-time "snapshot" of your in-memory data to a file (like a .json or binary file). * Why: Replaying an AOF log that has recorded millions of modifications over weeks takes a massive amount of time on system reboot. * How: Trigger a snapshot save every $N$ seconds or every $N$ write operations. When your database starts up: 1. Look for a snapshot file first and load it directly into memory. 2. Open your AOF log and only replay the commands recorded after that snapshot was taken. * Done when: You make millions of writes, restart the server, and it boots up instantly rather than spending minutes replaying every single historical write command. ## 5. AOF Rewrite / Compaction * What: A optimization background process that looks at the current data in memory and rewrites a clean, minimal AOF file, throwing away redundant historical commands. * Why: If a client updates the exact same key 10,000 times (e.g., SET score 1 up to SET score 10000), the AOF log holds 10,000 lines. However, the database only cares about the final state (SET score 10000). * How: You iterate through all keys currently active in your memory structure and write a brand new AOF file containing a single setup command for each active key. You then swap the old massive file for this clean, compacted one. * Done when: Run a loop updating a single key thousands of times. Trigger the rewrite, check the file size, and verify it shrank down to just one command line. ## 6. Data Structures Beyond Strings * What: Expanding your key-value store to support Lists instead of just single string values. * Commands to build: * LPUSH / RPUSH: Add items to the left (front) or right (back) of the list. * LPOP / RPOP: Remove and return items from the left or right. * LRANGE: Retrieve a range of items using start/stop boundaries, including negative numbers (e.g., -1 meaning the last item). ------------------------------ ## Part 2: Implementation Mechanics (Items 1–7)## 1. aof.py & fsync Policy * What: Separate the logging engine into its own module (aof.py). It formats every successful write operation into the RESP (REdis Serialization Protocol) format before appending it to disk. * Fsync Policies: Controls how safely data is written from volatile memory buffers onto physical disk sectors: * always: Forces a disk sync on every single write. Ultra-safe, but incredibly slow. * everysec: Buffers writes and flushes them to disk once per second. The industry standard balance of speed and safety. * no: Let the operating system decide when to flush the buffer. Fastest, but risky. ## 2. TTLs Written as Absolute Unix Time * What: When a key has a Time-To-Live expiration (e.g., "expire in 10 seconds"), convert that instantly into an absolute future timestamp (like 1789463400) before saving it to the AOF. * Why: If you use relative time ("10 seconds from now"), and the server crashes, remains offline for an hour, and then reboots—replaying that relative log would give the key a fresh 10 seconds of life, which is incorrect. Absolute timestamps ensure expired keys remain expired upon reboot. ## 3. Replay on Startup & Graceful Shutdown * What: Ensure reliability across the lifecycle of the process. * Startup: Before listening to new client connections, read your persistence files to reconstruct the state exactly as it was. * Shutdown: Trap system signals like Ctrl+C (SIGINT) or a termination instruction (SIGTERM) to flush any remaining in-memory buffers to disk and cleanly close files before exiting. ## 4. The Crash Test (kill -9) * What: A hard test of durability. * How: Write data with active expirations, then forcefully terminate the process using kill -9 (which prevents the program from running any graceful cleanup routines). Restart the system and verify the data structures and remaining expiration times are accurate. ## 5. Type Tagging & WRONGTYPE Error * What: Because your store now supports multiple data structures (Strings and Lists), every entry value needs a structural marker tag identifying its type. * How: Implement a TYPE <key> command. If a user attempts to execute a list command like LPUSH on a key that currently holds a plain string, return a explicit WRONGTYPE Operation against a key holding the wrong kind of value error. ## 6. Choosing a Underlying Data Structure (List vs. Deque) * Recommendation: Use collections.deque over Python’s standard list. * Justification: * Python's native list is optimized for fast access and appending at the end, but inserting or removing items from the left side (list.insert(0, x) or list.pop(0)) requires shifting every other item in memory, scaling poorly at $O(N)$ time complexity. * A deque (double-ended queue) is built as a doubly-linked list. It handles insertions and deletions at both the left and right ends in constant $O(1)$ time, matching Redis performance traits. ## 7. Command & Replay Testing * What: Write comprehensive functional tests verifying every list operation alters memory correctly. Crucially, write tests checking that if you perform a series of list operations (e.g., RPUSH, LPUSH, LPOP), the compiled AOF file parses perfectly back into the exact same list structure upon server restart. ------------------------------ To help you get started on the right path, would you like to see a core code skeleton for the OrderedDict LRU mechanism or a basic parser setup for the RESP format? part2 explain me       
Here is a simple, plain-English breakdown of Part 2 (Implementation Mechanics) for building your custom database store:

1. Separate Logging File (aof.py) & How Disk Saving Works (fsync)

• What it means: Put all your disk-writing code into its own file (aof.py). Every time a user changes data, convert that command into a strict text format (called RESP) before saving it.
• The 3 ways to save to your hard drive:
	• always: Save to disk immediately on every single write. It is 100% safe against power loss, but it makes your database run very slowly.
	• everysec: Collect writes in temporary memory and push them to disk once every second. This is the best balance of speed and safety.
	• no: Let your computer's operating system decide when to flush data to disk. It is super fast, but if the power cuts out, you might lose recent data.

2. Expiration Times (TTLs) Using Real Clock Time

• What it means: Instead of saving "this expires in 10 seconds," convert it to an exact future wall-clock timestamp (like a Unix epoch time, e.g., 1789463400).
• Why: If you save "10 seconds from now," and your server crashes for 5 minutes before restarting, a relative timer would falsely give the key 10 new seconds of life. Using an absolute timestamp ensures that if time has already passed, the key immediately dies upon reboot.

3. Starting Up and Shutting Down Safely

• What it means:
	• Startup: Before you let any users connect or send commands, load your old saved files first so your memory matches what it was before.
	• Shutdown: When someone presses Ctrl+C or stops the program, catch that signal first. Flush any leftover data sitting in memory out to the disk, close your files properly, and then turn off.

4. The Hard Crash Test (kill -9)

• What it means: You pull the plug or kill the process brutally (using kill -9), which doesn't let the program run its safe shutdown code.
• Why you do it: To see if your database can survive a sudden power outage. When you boot it back up, check if your data and timer countdowns are still accurate.

5. Labeling Data Types & Catching Type Mistakes

• What it means: Because you now store different kinds of data (like plain text Strings vs. ordered Lists), tag every value with a label saying what it is.
• How it works: Build a TYPE <key> command. If a user tries to run a list command (like adding an item to the left with LPUSH) on a key that actually holds a normal text string, throw an error message: WRONGTYPE Operation against a key holding the wrong kind of value.

6. Choosing the Right Tool: List vs. Deque

• What it means: Do not use Python's built-in list for your lists. Use Python’s collections.deque instead.
• Why:
	• A regular Python list has to shift every single item over in memory whenever you add or remove something from the front, which gets very slow as your list grows.
	• A deque (double-ended queue) lets you add or remove items from both the left and right sides instantly at maximum speed.

7. Testing Your Commands and Restarts

• What it means: Write automated tests for all your list commands.
• Why you do it: Make sure that if you push, pull, and pop items around, then shut down and restart, reading the log file recreates the exact same list in memory.
"""