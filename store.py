import time
from typing import Dict, Any, Optional, Callable

class Store:
    """An in-memory key-value data store with TTL expiration capabilities."""
    
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._data: Dict[str, Any] = {}
        self._expires: Dict[str, float] = {}  # Maps key -> absolute expiration timestamp
        self._clock = clock

    def _is_expired(self, key: str) -> bool:
        """Internal helper to check if a key has passed its time-to-live."""
        if key not in self._expires:
            return False
        if self._clock() >= self._expires[key]:
            self.delete(key)  # Lazy deletion on access
            return True
        return False

    def set(self, key: str, value: Any) -> str:
        """Sets a key to hold a value. Removes any existing TTL."""
        self._data[key] = value
        self._expires.pop(key, None)
        return "OK"

    def get(self, key: str) -> Optional[Any]:
        """Gets the value of a key. Returns None if expired or non-existent."""
        if self._is_expired(key) or key not in self._data:
            return None
        return self._data[key]

    def delete(self, key: str) -> int:
        """Deletes a key. Returns 1 if deleted, 0 if it did not exist."""
        self._expires.pop(key, None)
        if key in self._data:
            del self._data[key]
            return 1
        return 0

    def exists(self, key: str) -> int:
        """Checks if a key exists and is not expired. Returns 1 or 0."""
        if self._is_expired(key) or key not in self._data:
            return 0
        return 1

    def expire(self, key: str, seconds: int) -> int:
        """Sets a timeout on a key in seconds. Returns 1 if successful, 0 if no key."""
        if self._is_expired(key) or key not in self._data:
            return 0
        self._expires[key] = self._clock() + seconds
        return 1

    def ttl(self, key: str) -> int:
        """
        Returns the remaining time to live of a key that has a timeout.
        Returns -1 if the key exists but has no associated expire.
        Returns -2 if the key does not exist or is expired.
        """
        if self._is_expired(key) or key not in self._data:
            return -2
        if key not in self._expires:
            return -1
        remaining = self._expires[key] - self._clock()
        return max(0, int(round(remaining)))
