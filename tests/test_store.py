import pytest

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
