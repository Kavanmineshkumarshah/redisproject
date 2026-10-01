from datetime import datetime
from freezegun import freeze_time

# Approach A: As a Decorator
@freeze_time("2026-10-01 12:00:00")
def test_something():
    # Inside this function, the clock is frozen
    assert datetime.now() == datetime(2026, 10, 1, 12, 0, 0)

# Approach B: As a Context Manager
def test_another_thing():
    print(datetime.now()) # Returns the actual current time
    
    with freeze_time("2026-10-01 12:00:00"):
        print(datetime.now()) # Returns 2026-10-01 12:00:00
        
    print(datetime.now()) # Returns the actual current time again
