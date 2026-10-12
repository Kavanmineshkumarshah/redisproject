import sys
import os
import bisect

class RedisLite:
    def __init__(self, aof_path="appendonly.aof"):
        self.db = {}        # Holds the data structures
        self.types = {}     # Tracks the type of each key ('hash', 'set', 'zset')
        self.aof_path = aof_path
        self._clear_aof()

    def _clear_aof(self):
        """Initializes or clears the AOF file for a clean run."""
        with open(self.aof_path, "w") as f:
            f.write("")

    def _log_to_aof(self, cmd_args):
        """Appends mutating commands to the AOF file."""
        with open(self.aof_path, "a") as f:
            f.write(" ".join(map(str, cmd_args)) + "\n")

    def _check_type(self, key, expected_type):
        """Enforces Redis WRONGTYPE rules across all data types."""
        if key in self.types and self.types[key] != expected_type:
            return False
        return True

    # ==========================================
    # 1. HASHES (HSET, HGET, HGETALL)
    # ==========================================
    def hset(self, key, pairs):
        if not self._check_type(key, 'hash'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        
        if key not in self.db:
            self.db[key] = {}
            self.types[key] = 'hash'
        
        count = 0
        # Process pairs sequentially
        for i in range(0, len(pairs), 2):
            f, v = pairs[i], pairs[i+1]
            if f not in self.db[key]:
                count += 1
            self.db[key][f] = v
            
        self._log_to_aof(["HSET", key] + pairs)
        return count

    def hget(self, key, field):
        if not self._check_type(key, 'hash'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        if key not in self.db or field not in self.db[key]:
            return "(nil)"
        return self.db[key][field]

    def hgetall(self, key):
        if not self._check_type(key, 'hash'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        if key not in self.db:
            return "(empty array)"
        
        result = []
        for f, v in self.db[key].items():
            result.append(f)
            result.append(v)
        return result

    # ==========================================
    # 2. SETS (SADD, SMEMBERS, SINTER)
    # ==========================================
    def sadd(self, key, members):
        if not self._check_type(key, 'set'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        
        if key not in self.db:
            self.db[key] = set()
            self.types[key] = 'set'
            
        count = 0
        for m in members:
            if m not in self.db[key]:
                self.db[key].add(m)
                count += 1
                
        self._log_to_aof(["SADD", key] + members)
        return count

    def smembers(self, key):
        if not self._check_type(key, 'set'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        if key not in self.db:
            return "(empty array)"
        return sorted(list(self.db[key]))

    def sinter(self, keys):
        # Validate types for all participating keys
        for k in keys:
            if k in self.types and self.types[k] != 'set':
                return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        
        # If any requested key doesn't exist, intersection is empty
        for k in keys:
            if k not in self.db:
                return "(empty array)"
                
        # Optimization: Sort keys to loop over the smallest set first
        sorted_keys = sorted(keys, key=lambda k: len(self.db[k]))
        smallest_key = sorted_keys[0]
        
        intersect = set(self.db[smallest_key])
        for k in sorted_keys[1:]:
            intersect = intersect.intersection(self.db[k])
            if not intersect: 
                break
                
        return sorted(list(intersect))

    # ==========================================
    # 3. SORTED SETS (ZADD, ZRANGE)
    # ==========================================
    def zadd(self, key, pairs):
        if not self._check_type(key, 'zset'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
            
        if key not in self.db:
            # Main structure: dict for O(1) lookups, list for ordered entries
            self.db[key] = {'dict': {}, 'list': []}
            self.types[key] = 'zset'
            
        count = 0
        zset = self.db[key]
        
        for i in range(0, len(pairs), 2):
            score = float(pairs[i])
            member = pairs[i+1]
            
            # Re-ZADD optimization: if member exists, remove old score element to allow move
            if member in zset['dict']:
                old_score = zset['dict'][member]
                zset['list'].remove((old_score, member))
            else:
                count += 1
                
            zset['dict'][member] = score
            # Maintained order inside the list using bisect.insort
            bisect.insort(zset['list'], (score, member))
            
        self._log_to_aof(["ZADD", key] + pairs)
        return count

    def zrange(self, key, start, stop, with_scores=False):
        if not self._check_type(key, 'zset'):
            return "ERR WRONGTYPE Operation against a key holding the wrong kind of value"
        if key not in self.db:
            return "(empty array)"
            
        zlist = self.db[key]['list']
        n = len(zlist)
        
        # Handle Python-style negative indices manually to mimic Redis
        start = int(start)
        stop = int(stop)
        if start < 0: start = max(n + start, 0)
        if stop < 0: stop = max(n + stop, 0)
        
        sliced = zlist[start:stop+1]
        
        result = []
        for score, m in sliced:
            if with_scores:
                result.append(m)
                result.append(str(score))
            else:
                result.append(m)
        return result if result else "(empty array)"


def main():
    kv = RedisLite()
    print("RedisLite engine ready. Send line-separated inputs below:\n", flush=True)
    
    for line in sys.stdin:
        parts = line.strip().split()
        if not parts:
            continue
            
        cmd = parts[0].upper()
        
        if cmd == "HSET":
            # format: HSET key field value [field value ...]
            res = kv.hset(parts[1], parts[2:])
            print(f"(integer) {res}")
        elif cmd == "HGET":
            print(kv.hget(parts[1], parts[2]))
        elif cmd == "HGETALL":
            res = kv.hgetall(parts[1])
            print(res if isinstance(res, str) else "\n".join(f'{i+1}) "{v}"' for i, v in enumerate(res)))
            
        elif cmd == "SADD":
            res = kv.sadd(parts[1], parts[2:])
            print(f"(integer) {res}")
        elif cmd == "SMEMBERS":
            res = kv.smembers(parts[1])
            print(res if isinstance(res, str) else "\n".join(f'{i+1}) "{v}"' for i, v in enumerate(res)))
        elif cmd == "SINTER":
            res = kv.sinter(parts[1:])
            print(res if isinstance(res, str) else "\n".join(f'{i+1}) "{v}"' for i, v in enumerate(res)))
            
        elif cmd == "ZADD":
            res = kv.zadd(parts[1], parts[2:])
            print(f"(integer) {res}")
        elif cmd == "ZRANGE":
            # ZRANGE key start stop [WITHSCORES]
            with_scores = len(parts) > 4 and parts[4].upper() == "WITHSCORES"
            res = kv.zrange(parts[1], parts[2], parts[3], with_scores)
            print(res if isinstance(res, str) else "\n".join(f'{i+1}) "{v}"' for i, v in enumerate(res)))
        else:
            print(f"(error) ERR unknown command '{cmd}'")
            
        sys.stdout.flush()

if __name__ == "__main__":
    main()
