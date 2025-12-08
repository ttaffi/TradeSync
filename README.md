# Trade Republic Transaction Exporter

A Python automation script that exports Trade Republic transactions using `pytr`, maintains an incremental CSV file in a Git repository, and automatically commits and pushes updates. Designed for integration with Google Sheets via `IMPORTDATA`.

## Overview

This tool automates the export of your Trade Republic transaction history and maintains it as a stable CSV file in a Git repository. The CSV file is updated incrementally (only new transactions are appended), ensuring that:

- Existing rows remain unchanged (preserving Google Sheets formulas)
- The CSV file path and name never change (maintaining stable `IMPORTDATA` URLs)
- All changes are tracked in Git with automatic commits and pushes
- Backups are created before each update

## Features

- **Interactive Setup**: Guided configuration on first run
- **Incremental Updates**: Only appends new transactions, never overwrites existing data
- **Automatic Backups**: Creates timestamped backups before each update
- **Git Integration**: Automatically commits and pushes changes
- **Robust Transaction Detection**: Uses full row comparison to identify new transactions
- **Error Handling**: Clear error messages and graceful failure handling
- **CSV Format Compliance**: Strictly respects Trade Republic CSV format (semicolon delimiter, UTF-8)

## Prerequisites

- **macOS** (the script is designed for macOS, though it may work on Linux with minor modifications)
- **Python 3.7+** (for running the script)
- **Git** (installed and configured with working credentials)
- **uv** (Python package installer - will be checked and installation instructions provided if missing)
- **pytr** (accessed via `uv` - no global installation needed)
- **A Git repository** (the "data repo") where the CSV file will be stored

## Installation

1. **Clone or download this repository** to your local machine:
   ```bash
   git clone <your-repo-url> tr_exporter
   cd tr_exporter
   ```

2. **Make the script executable**:
   ```bash
   chmod +x src/update_transactions.py
   ```

3. **Ensure Python 3 is available**:
   ```bash
   python3 --version
   ```

4. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   source $HOME/.cargo/env
   ```

## Initial Setup

### First Run (Interactive Setup)

On the first run, the script will guide you through configuration:

```bash
python3 src/update_transactions.py
```

Or if you prefer to run setup explicitly:

```bash
python3 src/update_transactions.py setup
```

The setup will ask for:

1. **Target Repository Path**: The absolute path to your Git repository where the CSV will be stored
   - Example: `/Users/myuser/projects/trade-republic-transactions-data`
   - The directory must exist or you can choose to create it

2. **CSV File Name**: The name of the CSV file inside the data repo
   - Default: `account_transactions.csv`
   - This name should never change after setup

3. **Backup Directory Name**: Name of the directory where backups will be stored
   - Default: `backups`
   - Backups are stored inside the data repo

4. **Git Branch Name**: The branch to commit and push to
   - Default: `main`

5. **pytr Command**: The command to run pytr via uv
   - Default: `uvx pytr@latest export_transactions`
   - You can customize this if needed

After setup, the configuration is saved to `config.json` in the project root.

### Data Repository Setup

Before running the script, ensure you have a Git repository set up for storing the CSV:

```bash
# Create or navigate to your data repository
mkdir -p ~/projects/trade-republic-transactions-data
cd ~/projects/trade-republic-transactions-data

# Initialize Git repository (if not already initialized)
git init

# Add a remote (replace with your actual repository URL)
git remote add origin https://github.com/yourusername/trade-republic-transactions-data.git

# Create initial commit (optional, but recommended)
touch README.md
git add README.md
git commit -m "Initial commit"
git push -u origin main
```

**Important**: The data repository should be separate from this code repository. The script will work with any Git repository path you configure.

## Usage

### Normal Operation

After initial setup, simply run:

```bash
python3 src/update_transactions.py
```

The script will:

1. Check prerequisites (uv, Git)
2. Run `pytr` via `uv` (you'll be prompted for Trade Republic login credentials)
3. Compare the export with the existing CSV
4. Create a backup of the current CSV
5. Append only new transactions
6. Commit and push changes to Git

**Note**: The only interactive prompts during normal operation come from `pytr` itself (phone number, PIN, one-time code). The script runs fully automated otherwise.

### Reconfiguration

To change configuration later, you have two options:

1. **Edit `config.json` directly** (recommended):
   ```bash
   # Edit the config file
   nano config.json
   # or use your preferred editor
   ```

2. **Rerun setup**:
   ```bash
   python3 src/update_transactions.py setup
   ```

### Manual Execution

You can run the script manually at any time:

```bash
cd /path/to/tr_exporter
python3 src/update_transactions.py
```

## Automation (Cron)

To run the script automatically, add a cron entry. On macOS, you can use `crontab`:

```bash
crontab -e
```

Add a line to run the script daily (example: 7:30 AM):

```bash
30 7 * * * cd /path/to/tr_exporter && /usr/bin/python3 src/update_transactions.py >> /path/to/tr_exporter/logs/cron.log 2>&1
```

Or weekly (example: every Monday at 8:00 AM):

```bash
0 8 * * 1 cd /path/to/tr_exporter && /usr/bin/python3 src/update_transactions.py >> /path/to/tr_exporter/logs/cron.log 2>&1
```

**Note**: When running via cron, `pytr`'s interactive login prompts will not work. You may need to handle authentication differently or run the script manually when credentials expire.

## Google Sheets Integration

### Getting the Raw GitHub URL

Once your data repository is pushed to GitHub, you can get the raw URL of your CSV file:

1. Navigate to your CSV file in the GitHub web interface
2. Click the "Raw" button (or right-click and "Copy link address")
3. The URL will look like:
   ```
   https://raw.githubusercontent.com/yourusername/trade-republic-transactions-data/main/account_transactions.csv
   ```

### Using IMPORTDATA in Google Sheets

In a Google Sheets cell, use:

```excel
=IMPORTDATA("https://raw.githubusercontent.com/yourusername/trade-republic-transactions-data/main/account_transactions.csv")
```

**Important Notes**:

- The URL must point to the `raw` version of the file (not the GitHub web interface)
- `IMPORTDATA` refreshes periodically, but you can force a refresh by:
  - File → Spreadsheet settings → Recalculation → On change and every minute
  - Or manually: File → Refresh data connections
- The CSV file path and name must never change, or the `IMPORTDATA` formula will break

### Alternative: Using Google Apps Script

For more control over refresh timing, you can use Google Apps Script:

```javascript
function importTransactions() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Transactions");
  var url = "https://raw.githubusercontent.com/yourusername/trade-republic-transactions-data/main/account_transactions.csv";
  var csvContent = UrlFetchApp.fetch(url).getContentText();
  var csvData = Utilities.parseCsv(csvContent, ';'); // Note: semicolon delimiter
  sheet.getRange(1, 1, csvData.length, csvData[0].length).setValues(csvData);
}
```

Then set up a time-driven trigger to run this function periodically.

## Configuration File

The configuration is stored in `config.json`:

```json
{
  "target_repo_path": "/Users/myuser/projects/trade-republic-transactions-data",
  "csv_master_path": "account_transactions.csv",
  "backup_dir_name": "backups",
  "git_branch": "main",
  "pytr_cmd": "uvx pytr@latest export_transactions"
}
```

### Configuration Fields

- **`target_repo_path`**: Absolute path to the Git repository containing the CSV
- **`csv_master_path`**: Filename (or relative path) of the CSV file inside the data repo
- **`backup_dir_name`**: Directory name for backups (inside the data repo)
- **`git_branch`**: Git branch to commit and push to
- **`pytr_cmd`**: Command to run pytr (typically via `uvx`)

## CSV Format

The script strictly respects the Trade Republic CSV format:

- **Encoding**: UTF-8
- **Delimiter**: Semicolon (`;`)
- **Header**: `Data;Tipo;Valore;Note;ISIN;Azioni;Commissioni;Tasse`
- **Date Format**: ISO datetime (e.g., `2023-04-03T14:30:58`)

The script uses Python's built-in `csv` module with `delimiter=";"` to ensure compatibility.

## How It Works

### Transaction Detection

The script uses full row comparison to detect new transactions:

1. Reads the existing master CSV file
2. Reads the new export from `pytr`
3. Converts rows to tuples for comparison: `tuple(row)`
4. Builds a set of existing rows for efficient lookup
5. Appends only rows that are not in the existing set

This approach is robust because:
- It doesn't rely on dates (which could have duplicates or missing data)
- It handles any CSV structure that `pytr` exports
- It preserves all existing rows exactly as they were

### Backup Strategy

Before updating the master CSV, the script:
1. Creates a timestamped backup in the `backups/` directory
2. Names backups like: `account_transactions_20250115_073045.csv`
3. Tracks backups in Git (they are added and committed)

### Git Workflow

For each run with new transactions:
1. `git add` the updated master CSV and any new backup files
2. `git commit` with a timestamped message
3. `git push` to the remote repository

If no new transactions are detected, the script exits cleanly without creating a commit.

## Troubleshooting

### "uv is not installed"

Follow the installation instructions provided by the script, or install manually:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### "Target repository path does not exist"

Ensure the path in `config.json` is correct and the directory exists. You can create it manually or rerun setup.

### "Target path is not a Git repository"

Initialize the directory as a Git repository:
```bash
cd /path/to/your/data/repo
git init
git remote add origin <your-remote-url>
```

### "git push failed"

Check that:
- Git credentials are configured correctly
- The remote repository exists and is accessible
- You have push permissions
- The branch name in config matches the remote branch

### "No new transactions detected"

This is normal if:
- You've already exported all available transactions
- No new transactions have occurred since the last export
- The script will exit cleanly in this case

### pytr login issues

The script does not handle Trade Republic authentication. All login prompts come from `pytr` itself. If you encounter authentication issues:
- Ensure your Trade Republic account credentials are correct
- Check that the Trade Republic app is accessible for one-time codes
- Verify that `pytr` is working correctly by running the command manually

## Project Structure

```
tr_exporter/
├── README.md                 # This file
├── CHANGELOG.md              # Version history
├── config.json               # Configuration (created by setup)
├── config.example.json       # Configuration template
├── .gitignore                # Git ignore rules
└── src/
    └── update_transactions.py # Main script
```

## License

[Add your license here]

## Contributing

[Add contribution guidelines if applicable]

## Support

For issues, questions, or contributions, please [open an issue or create a pull request in the repository].
