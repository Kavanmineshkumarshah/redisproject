from store import Store



class CommandHandler:
    """Handle Redis-like commands."""

    def __init__(self, store: Store):
        self.store = store

    def execute(self, command: list[str]):
        """Execute a command."""

        if not command:
            return "-ERR empty command"

        cmd = command[0].upper()

        try:
            if cmd == "SET":
                return self._set(command)

            if cmd == "GET":
                return self._get(command)

            if cmd == "EXISTS":
                return self._exists(command)

            if cmd in ("DEL", "DELETE"):
                return self._delete(command)

            if cmd == "EXPIRE":
                return self._expire(command)

            if cmd == "TTL":
                return self._ttl(command)

            if cmd == "PING":
                return "PONG"
            if cmd=="DBSIZE":
                return str(len(self.store._data))
            return "-ERR unknown command"

        except ValueError:
            return "-ERR invalid integer"

    def _set(self, command):
        if len(command) != 3:
            return "-ERR wrong number of arguments for SET"

        key = command[1]
        value = command[2]

        return self.store.set(key, value)

    def _get(self, command):
        if len(command) != 2:
            return "-ERR wrong number of arguments for GET"

        key = command[1]

        value = self.store.get(key)

        if value is None:
            return None

        return value

    def _exists(self, command):
        if len(command) != 2:
            return "-ERR wrong number of arguments for EXISTS"

        key = command[1]

        return 1 if self.store.exists(key) else 0

    def _delete(self, command):
        if len(command) != 2:
            return "-ERR wrong number of arguments for DELETE"

        key = command[1]

        return self.store.delete(key)

    def _expire(self, command):
        if len(command) != 3:
            return "-ERR wrong number of arguments for EXPIRE"

        key = command[1]
        seconds = int(command[2])

        return self.store.expire(key, seconds)

    def _ttl(self, command):
        if len(command) != 2:
            return "-ERR wrong number of arguments for TTL"

        key = command[1]

        return self.store.ttl(key)