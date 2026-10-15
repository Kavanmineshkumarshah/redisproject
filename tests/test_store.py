import time
import pytest

# =====================================================================
# IMPLEMENTATION: The Store class designed to work with your FakeClock
# =====================================================================
class Store:
    def __init__(self, clock=None):
        # Fallback to standard time.time if no custom clock is injected
        self.clock = clock if clock is not None else time.time
        self._data = {}
        self._expires = {}  # Map of key -> absolute expiration timestamp

    def _get_current_time(self) -> float:
        return self.clock()

    def _is_expired(self, key: str) -> bool:
        if key in self._expires:
            if self._get_current_time() >= self._expires[key]:
                # Proactively clean up expired key
                del self._data[key]
                del self._expires[key]
                return True
        return False

    def set(self, key: str, value: str) -> str:
        self._data[key] = value
        # Setting a key clears any existing TTL constraint (standard Redis behavior)
        if key in self._expires:
            del self._expires[key]
        return "OK"

    def get(self, key: str) -> str or None:
        if self._is_expired(key) or key not in self._data:
            return None
        return self._data[key]

    def exists(self, key: str) -> int:
        if self._is_expired(key) or key not in self._data:
            return 0
        return 1

    def delete(self, key: str) -> int:
        # Check expiration to ensure accuracy before deletion tracking
        expired = self._is_expired(key)
        if key in self._data and not expired:
            del self._data[key]
            if key in self._expires:
                del self._expires[key]
            return 1
        return 0

    def expire(self, key: str, seconds: float) -> int:
        if self._is_expired(key) or key not in self._data:
            return 0
        self._expires[key] = self._get_current_time() + seconds
        return 1

    def ttl(self, key: str) -> int:
        if self._is_expired(key) or key not in self._data:
            return -2
        if key not in self._expires:
            return -1
        # Calculate remaining time
        remaining = self._expires[key] - self._get_current_time()
        return int(max(0, remaining))


# =====================================================================
# TESTING HOOKS & FIXTURES
# =====================================================================
class FakeClock:
    def __init__(self, start_time: float = 0.0):
        self.current_time = start_time
    
    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float):
        self.current_time += seconds

@pytest.fixture
def store_and_clock():
    clock = FakeClock()
    store = Store(clock=clock)
    return store, clock


# =====================================================================
# YOUR 11 ARRANGE-ACT-ASSERT TEST CASES
# =====================================================================

# 1. Arrange-Act-Assert: SET & GET
def test_set_and_get(store_and_clock):
    store, _ = store_and_clock
    assert store.set("foo", "bar") == "OK"
    assert store.get("foo") == "bar"

# 2. Arrange-Act-Assert: GET non-existent
def test_get_non_existent(store_and_clock):
    store, _ = store_and_clock
    assert store.get("missing") is None

# 3. Arrange-Act-Assert: EXISTS (Found vs Missing)
def test_exists(store_and_clock):
    store, _ = store_and_clock
    store.set("foo", "bar")
    assert store.exists("foo") == 1
    assert store.exists("missing") == 0

# 4. Arrange-Act-Assert: DEL active key
def test_delete_existing_key(store_and_clock):
    store, _ = store_and_clock
    store.set("foo", "bar")
    assert store.delete("foo") == 1
    assert store.get("foo") is None

# 5. Arrange-Act-Assert: DEL missing key
def test_delete_missing_key(store_and_clock):
    store, _ = store_and_clock
    assert store.delete("missing") == 0

# 6. Arrange-Act-Assert: EXPIRE successfully sets timeout
def test_expire_sets_ttl(store_and_clock):
    store, _ = store_and_clock
    store.set("foo", "bar")
    assert store.expire("foo", 10) == 1
    assert store.ttl("foo") == 10

# 7. Arrange-Act-Assert: EXPIRE on missing key
def test_expire_missing_key(store_and_clock):
    store, _ = store_and_clock
    assert store.expire("missing", 10) == 0

# 8. Arrange-Act-Assert: Key expires after time increments
def test_key_expiration_after_time(store_and_clock):
    store, clock = store_and_clock
    store.set("foo", "bar")
    store.expire("foo", 5)
    
    clock.advance(6)  # Fast-forward time past threshold without sleep!
    assert store.get("foo") is None
    assert store.exists("foo") == 0

# 9. Arrange-Act-Assert: TTL codes (-1 for persistent, -2 for missing)
def test_ttl_status_codes(store_and_clock):
    store, clock = store_and_clock
    store.set("persistent", "value")
    assert store.ttl("persistent") == -1
    assert store.ttl("non-existent") == -2

# 10. Arrange-Act-Assert: SET clears out past TTL constraints
def test_set_overwrites_expiration(store_and_clock):
    store, clock = store_and_clock
    store.set("foo", "bar")
    store.expire("foo", 5)
    store.set("foo", "new_value")  # Should wipe the absolute timestamp map
    
    clock.advance(6)
    assert store.get("foo") == "new_value"
    assert store.ttl("foo") == -1

# 11. Arrange-Act-Assert: TTL code matches missing state post expiration
def test_ttl_after_expiration(store_and_clock):
    store, clock = store_and_clock
    store.set("foo", "bar")
    store.expire("foo", 5)
    
    clock.advance(6)  # Fast-forward time past threshold without sleep!
    assert store.ttl("foo") == -2  # Key should be considered expired and removed
