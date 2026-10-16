from datetime import datetime
from time import sleep
from freezegun import freeze_time
@freeze_time("2026-10-01 12:00:00")
def test_something():
    # Inside this function, the clock is frozen
    assert datetime.now() == datetime(2026, 10, 1, 12, 0, 0)
    sleep(2)
    fake_time = datetime.now()
    # Fixed: Removed the unused variable 'fake_clock'
    assert fake_time == datetime(2026, 10, 1, 12, 0, 0)  # Still frozen at the same time

# Approach B: As a Context Manager
def test_another_thing():
    print(datetime.now())  # Returns the actual current time
    # Fixed: Removed the unused variable 'fake_clock'
    sleep(2)  # Reduced from 10 to 2 seconds just for faster test execution
    
    with freeze_time("2026-10-01 12:00:00"):
        # Fixed: freezegun returns timezone-naive datetimes by default, 
        # so comparing or printing matches the exact frozen string.
        print(datetime.now())  # Returns 2026-10-01 12:00:00
        
    print(datetime.now())  # Returns the actual current time again

# To execute the functions and see them work:
if __name__ == "__main__":
    print("Running Approach A...")
    test_something()
    print("Approach A passed successfully!\n")

    print("Running Approach B...")
    test_another_thing()
    print("Approach B passed successfully!")

