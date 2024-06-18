# Sprint Branch Automation

This project automates the creation of sprint branches based on a fixed 15-day sprint cycle using a Python script and GitHub Actions.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Workflow](#workflow)
- [Contributing](#contributing)
- [License](#license)

## Overview

The purpose of this project is to automate the process of determining the start of a new sprint and creating a corresponding Git branch. The Python script calculates if today is the start of a new sprint based on a 15-day cycle and constructs a branch name. The GitHub Actions workflow runs the script daily and creates the branch if applicable.

## Features

- **Automated Sprint Calculation**: Determine the start of new sprints based on a fixed cycle.
- **Dynamic Branch Creation**: Automatically create and push sprint branches.
- **Daily Automation**: Runs daily at midnight UTC.
- **Manual Trigger**: Can be triggered manually via GitHub Actions.

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/yourusername/sprint-branch-automation.git
   cd sprint-branch-automation
2. Setup Python Environment:
Ensure you have Python 3.x installed. You can set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage
1. Run the Script Manually:
You can run the script manually to see if today is a sprint start day:
```bash
python scripts/calculate_sprint_details.py
```
2. Configure GitHub Actions:
Ensure the `create_sprint_branch.yml` file is located in the `.github/workflows/` directory of your repository.

## Workflow
[The GitHub Actions workflow](.github/workflows/create_sprint_branch.yml) is configured to run the Python script daily at midnight UTC. If today is determined to be a sprint start day, it creates a new branch named according to the calculated sprint details and pushes it to the remote repository.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss any changes or improvements.

## License
This project is licensed under the MIT License.