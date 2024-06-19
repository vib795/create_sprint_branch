import datetime
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the current date and time in UTC
today = datetime.datetime.now(datetime.timezone.utc)
logger.info(f"TODAY: {today}")
year = today.year
month = today.month
day = today.day

# Function to get the last Wednesday
def get_last_wednesday(date):
    days_behind = (date.weekday() + 4) % 7
    return date - datetime.timedelta(days=days_behind)

# Get the last Wednesday
last_wednesday = get_last_wednesday(today)
logger.info(f"LAST WEDNESDAY: {last_wednesday}")

# Check if today is a sprint start date (every 15 days starting from a reference date)
reference_date = datetime.datetime(2024, 6, 5, tzinfo=datetime.timezone.utc)  # Example start date
logger.info(f"REFERENCE DATE: {reference_date}")
delta_days = (today - reference_date).days
logger.info(f"DELTA DAYS: {delta_days}")
is_sprint_start = delta_days % 14 == 0

if is_sprint_start:
    # Calculate the quarter
    quarter = (month - 1) // 3 + 1

    # Calculate sprint number within the quarter
    first_day_of_quarter = datetime.datetime(year, 3 * (quarter - 1) + 1, 1, tzinfo=datetime.timezone.utc)
    days_since_quarter_start = (last_wednesday - first_day_of_quarter).days

    # Adjust sprint number calculation to ensure it's always positive
    if days_since_quarter_start >= 0:
        sprint_number = days_since_quarter_start // 15 + 1
    else:
        sprint_number = 1

    # Calculate end date of the sprint
    end_date = last_wednesday + datetime.timedelta(days=14)

    # Format the dates
    start_date_str = last_wednesday.strftime('%m%d%y')
    end_date_str = end_date.strftime('%m%d%y')

    # Form the branch name
    branch_name = f"Sprint_Q{quarter}_S{sprint_number}_{start_date_str}_{end_date_str}"
    logger.info(f"Branch name: {branch_name}")

    print(f"::set-output name=branch_name::{branch_name}")
else:
    logger.info("Today is not a sprint start date.")
    print("::set-output name=branch_name::skip")

sys.exit(0)
