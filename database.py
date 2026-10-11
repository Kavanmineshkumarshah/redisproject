import json
import os
import time
import signal
import sys
from collections import OrderedDict, deque
from typing import Any, Optional, List
from aof import AOFManager

class ValueWrapper:
    def __init__(self, data_type: str, value: Any, expire_at: Optional[float] = None):
        self.type = data_type      
        self.value = value        
        self.expire_at = expire_at

    def is_expired(self) -> bool:
        if self.expire_at is None:
            return False
        return time.time() > self.expire_at

class MicroRedis:
    def __init__(self, maxmemory: int = 5, fsync: str = "everysec",
                 snapshot_file: str = "dump.rdb", aof_file: str = "appendonly.aof"):
        self.maxmemory = maxmemory
        self.snapshot_file = snapshot_file
        self.aof_file = aof_file
        self.db: OrderedDict[str, ValueWrapper] = OrderedDict()
        self._load_from_storage()
        self.aof = AOFManager(filepath=self.aof_file, fsync=fsync)
       
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _mark_dirty_lru(self, key: str):
        if key in self.db:
            self.db.move_to_end(key)

    def _evict_if_needed(self):
        while len(self.db) > self.maxmemory:
            evicted_key, _ = self.db.popitem(last=False)
            print(f"⚠️ [Eviction Policy] Evicted key '{evicted_key}' due to maxmemory limit ({self.maxmemory}).")

    def _get_valid_entry(self, key: str) -> Optional[ValueWrapper]:
        if key not in self.db:
            return None
        entry = self.db[key]
        if entry.is_expired():
            del self.db[key]
            return None
        self._mark_dirty_lru(key)
        return entry

    # --- Core API Sets ---
    def set(self, key: str, value: str, ex_seconds: Optional[int] = None) -> str:
        expire_at = None
        if ex_seconds is not None:
            expire_at = time.time() + float(ex_seconds)
           
        self.db[key] = ValueWrapper("string", str(value), expire_at)
        self._mark_dirty_lru(key)
        self._evict_if_needed()
       
        aof_cmd = ["SET", key, value]
        if expire_at:
            aof_cmd += ["EXAT", str(expire_at)]
        self.aof.append(aof_cmd)
        return "OK"

    def get(self, key: str) -> Optional[str]:
        entry = self._get_valid_entry(key)
        if not entry:
            return None
        if entry.type != "string":
            return "(error) WRONGTYPE Operation against a key holding the wrong kind of value"
        return f'"{entry.value}"'

    def push(self, key: str, value: str, side: str = "right") -> Any:
        entry = self._get_valid_entry(key)
        if entry and entry.type != "list":
            return "(error) WRONGTYPE Operation against a key holding the wrong kind of value"
       
        if not entry:
            entry = ValueWrapper("list", deque())
            self.db[key] = entry
            self._evict_if_needed()
       
        if side == "left":
            entry.value.appendleft(value)
        else:
            entry.value.append(value)
           
        self._mark_dirty_lru(key)
        self.aof.append([f"{side.upper()}PUSH", key, value])
        return f"(integer) {len(entry.value)}"

    def pop(self, key: str, side: str = "right") -> Optional[str]:
        entry = self._get_valid_entry(key)
        if not entry:
            return "(nil)"
        if entry.type != "list":
            return "(error) WRONGTYPE Operation against a key holding the wrong kind of value"
        if not entry.value:
            return "(nil)"
           
        val = entry.value.popleft() if side == "left" else entry.value.pop()
        self._mark_dirty_lru(key)
        self.aof.append([f"{side.upper()}POP", key])
       
        if not entry.value:
            del self.db[key]
           
        return f'"{val}"'

    def lrange(self, key: str, start: int, stop: int) -> Any:
        entry = self._get_valid_entry(key)
        if not entry:
            return "(empty list or set)"
        if entry.type != "list":
            return "(error) WRONGTYPE Operation against a key holding the wrong kind of value"
       
        lst = list(entry.value)
        length = len(lst)
        start = start if start >= 0 else length + start
        stop = stop if stop >= 0 else length + stop
       
        result = lst[start : stop + 1]
        if not result:
            return "(empty list or set)"
       
        # Nicely format array output for the CLI
        return "\n".join(f'{i+1}) "{item}"' for i, item in enumerate(result))

    def type(self, key: str) -> str:
        entry = self._get_valid_entry(key)
        if not entry:
            return "none"
        return entry.type

    def save_snapshot(self) -> str:
        snapshot_data = {}
        for k, entry in list(self.db.items()):
            if not entry.is_expired():
                snapshot_data[k] = {
                    "type": entry.type,
                    "value": list(entry.value) if entry.type == "list" else entry.value,
                    "expire_at": entry.expire_at
                }
        with open(self.snapshot_file, "w") as f:
            json.dump(snapshot_data, f)
        return "OK (Snapshot Saved)"

    def rewrite_aof(self) -> str:
        temp_aof_path = self.aof_file + ".tmp"
        temp_aof = AOFManager(filepath=temp_aof_path, fsync="no")
       
        for k, entry in list(self.db.items()):
            if entry.is_expired():
                continue
            if entry.type == "string":
                cmd = ["SET", k, entry.value]
                if entry.expire_at:
                    cmd += ["EXAT", str(entry.expire_at)]
                temp_aof.append(cmd)
            elif entry.type == "list":
                for item in entry.value:
                    temp_aof.append(["RPUSH", k, item])
                if entry.expire_at:
                    temp_aof.append(["EXAT", k, str(entry.expire_at)])

        temp_aof.close()
        self.aof.close()
        os.replace(temp_aof_path, self.aof_file)
        self.aof = AOFManager(filepath=self.aof_file, fsync=self.aof.fsync)
        return "OK (AOF Compacted)"

    def _load_from_storage(self):
        if os.path.exists(self.snapshot_file):
            try:
                with open(self.snapshot_file, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    exp = v["expire_at"]
                    if exp and time.time() > exp:
                        continue
                    val = deque(v["value"]) if v["type"] == "list" else v["value"]
                    self.db[k] = ValueWrapper(v["type"], val, exp)
            except Exception:
                pass

        if os.path.exists(self.aof_file):
            commands = AOFManager.parse_resp(self.aof_file)
            for tokens in commands:
                if not tokens:
                    continue
                cmd = tokens[0].upper()
                if cmd == "SET":
                    key, val = tokens[1], tokens[2]
                    exp_at = None
                    if len(tokens) > 4 and tokens[3].upper() == "EXAT":
                        exp_at = float(tokens[4])
                    if exp_at and time.time() > exp_at:
                        continue
                    self.db[key] = ValueWrapper("string", val, exp_at)
                elif cmd in ("RPUSH", "LPUSH"):
                    key, val = tokens[1], tokens[2]
                    entry = self.db.get(key)
                    if not entry or entry.type != "list":
                        entry = ValueWrapper("list", deque())
                        self.db[key] = entry
                    if cmd == "LPUSH":
                        entry.value.appendleft(val)
                    else:
                        entry.value.append(val)
                elif cmd in ("RPOP", "LPOP"):
                    key = tokens[1]
                    entry = self.db.get(key)
                    if entry and entry.type == "list" and entry.value:
                        _ = entry.value.popleft() if cmd == "LPOP" else entry.value.pop()
                        if not entry.value:
                            del self.db[key]

    def _handle_shutdown(self, signum, frame):
        print(f"\n🛑 Safe shutdown triggered. Flushing AOF changes to disk...")
        self.aof.close()
        sys.exit(0)
