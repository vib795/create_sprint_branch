import datetime
import subprocess
import os

# Set the reference date and today's date for testing purposes
reference_date = datetime.datetime(2024, 6, 6, tzinfo=datetime.timezone.utc)
test_date = datetime.datetime(2024, 6, 20, tzinfo=datetime.timezone.utc)

# Mock datetime to return the test date
class MockDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return test_date

# Replace datetime in the calculate_sprint_details module
datetime.datetime = MockDateTime

# Ensure GITHUB_ENV is set for local testing
os.environ['GITHUB_ENV'] = './test.env'

# Run the calculate_sprint_details.py script
subprocess.run(["python", "scripts/calculate_sprint_details.py"])

# Restore the original datetime class
datetime.datetime = datetime.datetime.__class__

# Check the result
with open('./test.env', 'r') as env_file:
    for line in env_file:
        print(line.strip())
