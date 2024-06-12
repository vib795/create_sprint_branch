# scripts/calculate_sprint_details.py
import datetime
import sys

today = datetime.datetime.utcnow()
year = today.year
month = today.month
day = today.day

# Function to get the last Wednesday
def get_last_wednesday(date):
    days_behind = (date.weekday() + 4) % 7
    last_wednesday = date - datetime.timedelta(days=days_behind)
    return last_wednesday

# Get the last Wednesday
last_wednesday = get_last_wednesday(today)

# Check if today is a sprint start date (every 15 days starting from a reference date)
reference_date = datetime.datetime(2024, 6, 5) # Example start date
delta_days = (today - reference_date).days
is_sprint_start = delta_days % 15 == 0

if is_sprint_start:
    # Calculate the quarter
    quarter = (month - 1) // 3 + 1

    # Calculate sprint number within the quarter
    first_day_of_quarter = datetime.datetime(year, 3 * (quarter - 1) + 1, 1)
    days_since_quarter_start = (last_wednesday - first_day_of_quarter).days
    sprint_number = days_since_quarter_start // 15 + 1

    # Calculate end date of the sprint
    end_date = last_wednesday + datetime.timedelta(days=14)

    # Format the dates
    start_date_str = last_wednesday.strftime('%m%d%y')
    end_date_str = end_date.strftime('%m%d%y')

    # Form the branch name
    branch_name = f"Sprint_Q{quarter}_S{sprint_number}_{start_date_str}_{end_date_str}"

    print(f"::set-output name=branch_name::{branch_name}")
else:
    print("::set-output name=branch_name::skip")

sys.exit(0)
