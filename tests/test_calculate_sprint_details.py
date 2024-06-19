import datetime
import subprocess
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set the reference date and today's date for testing purposes
# reference_date = datetime.datetime(2024, 6, 4, tzinfo=datetime.timezone.utc)
test_date = datetime.datetime(2024, 6, 19, tzinfo=datetime.timezone.utc)

# logger.info(f"REFERENCE DATE: {reference_date}")
# logger.info(f"TEST DATE: {test_date}")

# Mock datetime to return the test date
class MockDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return test_date

# Replace datetime in the calculate_sprint_details module
datetime.datetime = MockDateTime

# Run the calculate_sprint_details.py script
subprocess.run(["python", "scripts/calculate_sprint_details.py"])

# Restore the original datetime class
datetime.datetime = datetime.datetime.__class__
