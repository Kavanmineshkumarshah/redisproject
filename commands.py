from ast import arg
import cmd
from logging import Handler
from turtle import st

from redisproject import store
from store import Store



class CommandHandler:
    """Handle Redis-like commands."""

"""    def __init__(self, store: Store):
        self.store = store

    def execute(self, command: list[str]):
        """ """

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

        return self.store.ttl(key)"""
def cmd_ping(store: Store, args: list[str]):
    return args[0] if args else "PONG"
def cmd_get(store: Store, args: list[str]):
    if len(args) != 1:
        return "-ERR wrong number of arguments for GET"
    return store.get(args[0])
def cmd_set(store: Store, args: list[str]):
    if len(args) != 2:
        return "-ERR wrong number of arguments for SET"
    return store.set(args[0], args[1])
def cmd_exists(store: Store, args: list[str]):
    if len(args) < 1:
        return "-ERR wrong number of arguments for EXISTS"
    return sum(store.exists(key) for key in args)
def cmd_delete(store: Store, args: list[str]):
    if len(args) < 1:
        return "-ERR wrong number of arguments for DELETE"
    return sum(store.delete(key) for key in args)
def cmd_expire(store: Store, args: list[str]):
    if len(args) != 2:
        return "-ERR wrong number of arguments for EXPIRE"
    key = args[0]
    try:
        seconds = int(args[1])
    except ValueError:
        return "-ERR value is not an integer or out of range"
    return store.expire(key, seconds)
def cmd_ttl(store: Store, args: list[str]):
    if len(args) != 1:
        return "-ERR wrong number of arguments for TTL"
    return store.ttl(args[0])
def cmd_dbsize(store: Store, args: list[str]):
    if len(args) != 0:
        return "-ERR wrong number of arguments for DBSIZE"
    return store.DBSIZE()


COMMANDS = {
    "PING": (cmd_ping, (0, 1)),
    "GET": (cmd_get, 1),
    "SET": (cmd_set, 2),
    "EXISTS": (cmd_exists, (1, None)),
    "DEL": (cmd_delete, (1, None)),
    "DELETE": (cmd_delete, (1, None)),
    "EXPIRE": (cmd_expire, 2),
    "TTL": (cmd_ttl, 1),
    "DBSIZE": (cmd_dbsize, 0),
}


class CommandHandler:
    """Dispatch Redis-like commands through the command registry."""

    def __init__(self, store: Store):
        self.store = store

    def execute(self, command: list[str]):
        if not command:
            return "-ERR empty command"

        name = command[0].upper()
        if name not in COMMANDS:
            return f"-ERR unknown command '{name}'"

        handler, arity = COMMANDS[name]
        args = command[1:]
        if isinstance(arity, tuple):
            minimum, maximum = arity
            valid_arity = len(args) >= minimum and (
                maximum is None or len(args) <= maximum
            )
        else:
            valid_arity = len(args) == arity

        if not valid_arity:
            return f"-ERR wrong number of arguments for '{name.lower()}' command"

        try:
            return handler(self.store, args)
        except ValueError:
            return "-ERR value is not an integer or out of range"
