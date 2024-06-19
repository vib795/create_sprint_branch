# Sprint Branch Automation

This project automates the creation of sprint branches based on a fixed 14-day sprint cycle using a Python script and GitHub Actions.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Workflow](#workflow)
- [Generating a Personal Access Token (PAT)](#generating-a-personal-access-token-pat)
- [Creating Secrets in GitHub](#creating-secrets-in-github)
- [Contributing](#contributing)
- [License](#license)

## Overview

The purpose of this project is to automate the process of determining the start of a new sprint and creating a corresponding Git branch. The Python script calculates if today is the start of a new sprint based on a 14-day cycle and constructs a branch name. The GitHub Actions workflow runs the script daily and creates the branch if applicable.

## Features

- **Automated Sprint Calculation**: Determine the start of new sprints based on a fixed cycle.
- **Dynamic Branch Creation**: Automatically create and push sprint branches.
- **Daily Automation**: Runs daily at midnight UTC.
- **Manual Trigger**: Can be triggered manually via GitHub Actions.

## Installation

1. **Clone the Repository**:
```bash
   git clone https://github.com/vib795/create_sprint_branch.git
   cd create_sprint_branch
```

2. **Setup Python Environment:**
Ensure you have Python 3.x installed. You can set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage
1. **Run the Script Manually:**
You can run the script manually to see if today is a sprint start day:
```bash
python scripts/calculate_sprint_details.py
```

2. **Configure GitHub Actions:**
Ensure the workflow file is located in the correct directory. 

Configure GitHub Actions: Ensure the `create_sprint_branch.yml` file is located in the `.github/workflows/` directory of your repository.


## Workflow
[The GitHub Actions workflow](https://github.com/vib795/create_sprint_branch/blob/master/.github/workflows/create_sprint_branch.yml) is configured to run the Python script daily at midnight UTC. If today is determined to be a sprint start day, it creates a new branch named according to the calculated sprint details and pushes it to the remote repository.

## Generating a Personal Access Token (PAT)
1. Go to GitHub Settings:
   - Navigate to your GitHub account settings by clicking on your profile picture in the top right corner and selecting Settings.

2. Generate a New Token:
   - In the left sidebar, click on Developer settings.
   - Click on Personal access tokens.
   - Click the Generate new token button.

3. Select Scopes:
   - Give your token a descriptive name.
   - Select the scopes, such as repo (Full control of private repositories).
   - Click Generate token.

4. Save the Token:
   - Copy the token and save it in a secure location. You will need it to create a secret in your GitHub repository.

## Creating Secrets in GitHub
1. Go to Your Repository:
   - Navigate to your GitHub repository.
   - Click on `Settings`.

2. Add a New Secret:
   - In the left sidebar, click on `Secrets and variables`, then `Actions`.
   - Click the `New repository` secret button.
   - Name the secret `GH_PAT` and paste your personal access token in the value field.
   - Click `Add secret`.

## Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss any changes or improvements.

## License
This project is licensed under the MIT License.