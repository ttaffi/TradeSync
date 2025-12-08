#!/usr/bin/env python3
"""
Trade Republic Transaction Exporter

This script automates the export of Trade Republic transactions using pytr,
maintains an incremental CSV file in a Git repository, and commits/pushes updates.

Main steps:
1. Check for configuration file, run interactive setup if missing
2. Validate prerequisites (uv, Git)
3. Run pytr via uv to export transactions
4. Load existing master CSV and compare with new export
5. Create backup of existing CSV
6. Append only new transactions to master CSV (preserving exact format)
7. Commit and push changes to Git repository

The script respects the Trade Republic CSV format exactly:
- UTF-8 encoding, semicolon (;) delimiter
- Header: Data;Tipo;Valore;Note;ISIN;Azioni;Commissioni;Tasse
- All rows treated as strings, compared using tuple(row) for deduplication
"""

import json
import os
import sys
import subprocess
import shutil
import csv
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set


# CSV format constants
FIELDNAMES = ["Data", "Tipo", "Valore", "Note", "ISIN", "Azioni", "Commissioni", "Tasse"]
CSV_DELIMITER = ";"
CSV_ENCODING = "utf-8"

# Configuration file name
CONFIG_FILE = "config.json"
CONFIG_EXAMPLE = "config.example.json"

# Script directory (where this file lives)
SCRIPT_DIR = Path(__file__).parent.parent
CONFIG_PATH = SCRIPT_DIR / CONFIG_FILE


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"ERROR: {message}", file=sys.stderr)


def print_info(message: str) -> None:
    """Print info message to stdout."""
    print(f"INFO: {message}")


def check_uv_installed() -> bool:
    """Check if uv is installed and available."""
    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_uv_instructions() -> str:
    """Return instructions for installing uv on macOS."""
    return """
uv is not installed. To install uv on macOS, run:

    curl -LsSf https://astral.sh/uv/install.sh | sh

After installation, restart your terminal or run:

    source $HOME/.cargo/env

Then try running this script again.
"""


def load_config() -> Optional[Dict]:
    """Load configuration from config.json file."""
    if not CONFIG_PATH.exists():
        return None
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = [
            'target_repo_path',
            'csv_master_path',
            'backup_dir_name',
            'git_branch',
            'pytr_cmd'
        ]
        
        for field in required_fields:
            if field not in config:
                print_error(f"Config file missing required field: {field}")
                return None
        
        return config
    except json.JSONDecodeError as e:
        print_error(f"Config file is not valid JSON: {e}")
        return None
    except Exception as e:
        print_error(f"Error reading config file: {e}")
        return None


def interactive_setup() -> Dict:
    """Run interactive setup to collect configuration from user."""
    print("\n" + "="*60)
    print("Trade Republic Transaction Exporter - Setup")
    print("="*60)
    print("\nThis setup will collect the configuration needed to run the exporter.")
    print("You can edit config.json later if you need to change these values.\n")
    
    config = {}
    
    # Target repo path
    while True:
        target_repo = input("Enter the path to your Git data repository (e.g., /Users/myuser/projects/trade-republic-transactions-data): ").strip()
        if not target_repo:
            print("Path cannot be empty. Please try again.")
            continue
        target_repo_path = Path(target_repo).expanduser().resolve()
        if not target_repo_path.exists():
            print(f"Warning: Path does not exist: {target_repo_path}")
            create = input("Create this directory? (y/n): ").strip().lower()
            if create == 'y':
                target_repo_path.mkdir(parents=True, exist_ok=True)
            else:
                print("Please enter an existing path or choose 'y' to create it.")
                continue
        config['target_repo_path'] = str(target_repo_path)
        break
    
    # CSV master path
    csv_name = input("Enter CSV file name inside the data repo (default: account_transactions.csv): ").strip()
    if not csv_name:
        csv_name = "account_transactions.csv"
    config['csv_master_path'] = csv_name
    
    # Backup directory
    backup_dir = input("Enter backup directory name inside the data repo (default: backups): ").strip()
    if not backup_dir:
        backup_dir = "backups"
    config['backup_dir_name'] = backup_dir
    
    # Git branch
    git_branch = input("Enter Git branch name (default: main): ").strip()
    if not git_branch:
        git_branch = "main"
    config['git_branch'] = git_branch
    
    # pytr command
    pytr_cmd = input("Enter pytr command via uv (default: uvx pytr@latest export_transactions): ").strip()
    if not pytr_cmd:
        pytr_cmd = "uvx pytr@latest export_transactions"
    config['pytr_cmd'] = pytr_cmd
    
    # Save config
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"\n✓ Configuration saved to {CONFIG_PATH}")
    except Exception as e:
        print_error(f"Failed to save config file: {e}")
        sys.exit(1)
    
    # Print summary
    print("\n" + "="*60)
    print("Configuration Summary")
    print("="*60)
    for key, value in config.items():
        print(f"  {key}: {value}")
    print("="*60 + "\n")
    
    return config


def run_pytr_export(pytr_cmd: str, output_file: Path) -> bool:
    """Run pytr command and write CSV directly to output file.
    
    pytr export_transactions accepts an outputfile argument, so we pass
    the file path directly to pytr instead of capturing stdout/stderr.
    Shows all pytr output to terminal.
    """
    print_info(f"Running pytr export: {pytr_cmd}")
    print_info("Note: pytr will prompt you for Trade Republic login credentials.")
    
    # Split command into list for subprocess
    cmd_parts = pytr_cmd.split()
    
    # Add the output file path as the last argument to pytr
    # pytr export_transactions accepts: [outputfile] as positional argument
    cmd_parts.append(str(output_file))
    
    try:
        # Run pytr: let stdout and stderr go to terminal so user sees all output
        # pytr will write the CSV directly to the output_file path
        result = subprocess.run(
            cmd_parts,
            stdout=None,  # Let stdout go to terminal
            stderr=None,  # Let stderr go to terminal
            stdin=sys.stdin,  # Allow interactive input for pytr login
            text=True,
            check=True
        )
        
        # Verify output file was created and is not empty
        if not output_file.exists():
            print_error("pytr did not create the output CSV file")
            return False
        
        if output_file.stat().st_size == 0:
            print_error("pytr export produced an empty CSV file")
            return False
        
        print_info(f"Export completed. CSV saved to: {output_file}")
        return True
        
    except subprocess.CalledProcessError as e:
        print_error(f"pytr export failed (exit code {e.returncode})")
        return False
    except Exception as e:
        print_error(f"Error running pytr: {e}")
        return False


def read_csv_rows(csv_path: Path) -> Tuple[Optional[List[str]], List[List[str]]]:
    """Read CSV file and return (header, data_rows).
    
    Returns:
        (header_list, data_rows_list) where header may be None if no header exists.
        All rows are returned as lists of strings.
    """
    if not csv_path.exists():
        return (None, [])
    
    # Check if file is empty
    if csv_path.stat().st_size == 0:
        return (None, [])
    
    header = None
    rows = []
    try:
        with open(csv_path, 'r', encoding=CSV_ENCODING, newline='') as f:
            reader = csv.reader(f, delimiter=CSV_DELIMITER)
            
            # Read header
            header = next(reader, None)
            
            # Read all data rows
            for row in reader:
                # Skip completely empty rows
                if not any(row):
                    continue
                rows.append(row)
    except Exception as e:
        print_error(f"Error reading CSV file {csv_path}: {e}")
        return (None, [])
    
    return (header, rows)


def write_csv_rows(csv_path: Path, header: List[str], rows: List[List[str]]) -> bool:
    """Write CSV file with header and rows.
    
    Args:
        csv_path: Path to write CSV file
        header: Header row as list of strings
        rows: Data rows as list of lists of strings
    """
    try:
        # Ensure parent directory exists
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(csv_path, 'w', encoding=CSV_ENCODING, newline='') as f:
            writer = csv.writer(f, delimiter=CSV_DELIMITER)
            
            # Write header
            if header:
                writer.writerow(header)
            else:
                writer.writerow(FIELDNAMES)
            
            # Write data rows
            writer.writerows(rows)
        
        return True
    except Exception as e:
        print_error(f"Error writing CSV file {csv_path}: {e}")
        return False


def create_backup(source_file: Path, backup_dir: Path) -> Optional[Path]:
    """Create a timestamped backup of the source file."""
    if not source_file.exists():
        return None
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{source_file.stem}_{timestamp}{source_file.suffix}"
    backup_path = backup_dir / backup_name
    
    try:
        shutil.copy2(source_file, backup_path)
        print_info(f"Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print_error(f"Failed to create backup: {e}")
        return None


def find_new_transactions(existing_rows: List[List[str]], new_rows: List[List[str]]) -> List[List[str]]:
    """Find transactions in new_rows that are not in existing_rows.
    
    Uses tuple(row) for comparison to handle all fields.
    """
    # Build set of existing rows for efficient lookup
    existing_set: Set[Tuple[str, ...]] = {tuple(row) for row in existing_rows}
    
    # Find new transactions
    new_transactions = []
    for row in new_rows:
        if tuple(row) not in existing_set:
            new_transactions.append(row)
    
    return new_transactions


def git_add_file(repo_path: Path, file_path: Path) -> bool:
    """Run git add on a file in the repository."""
    try:
        # Convert absolute path to relative path from repo root
        try:
            relative_path = file_path.relative_to(repo_path)
        except ValueError:
            # If file_path is not relative to repo_path, use it as-is
            relative_path = file_path
        
        result = subprocess.run(
            ["git", "add", str(relative_path)],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"git add failed: {e.stderr}")
        return False


def git_commit(repo_path: Path, message: str) -> bool:
    """Create a git commit in the repository.
    
    Returns True if commit was created, False if nothing to commit.
    """
    try:
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print_info(f"Commit created: {message}")
        return True
    except subprocess.CalledProcessError as e:
        # Check if it's a "nothing to commit" case
        if "nothing to commit" in e.stdout.lower() or "nothing to commit" in e.stderr.lower():
            return False
        print_error(f"git commit failed: {e.stderr}")
        return False


def git_push(repo_path: Path, branch: str) -> bool:
    """Push commits to remote repository."""
    try:
        result = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        print_info(f"Pushed to origin/{branch}")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"git push failed: {e.stderr}")
        return False


def main():
    """Main script entry point."""
    # Check for setup mode
    setup_mode = len(sys.argv) > 1 and sys.argv[1] == "setup"
    
    # Load or create configuration
    config = load_config()
    
    if not config or setup_mode:
        if setup_mode:
            print_info("Running in setup mode...")
        else:
            print_info("Configuration file not found. Starting setup...")
        config = interactive_setup()
    
    # Validate prerequisites
    if not check_uv_installed():
        print_error(install_uv_instructions())
        sys.exit(1)
    
    # Extract configuration
    target_repo_path = Path(config['target_repo_path']).expanduser().resolve()
    csv_master_path = target_repo_path / config['csv_master_path']
    backup_dir = target_repo_path / config['backup_dir_name']
    git_branch = config['git_branch']
    pytr_cmd = config['pytr_cmd']
    
    # Validate target repo exists
    if not target_repo_path.exists():
        print_error(f"Target repository path does not exist: {target_repo_path}")
        sys.exit(1)
    
    # Check if it's a git repository
    if not (target_repo_path / ".git").exists():
        print_error(f"Target path is not a Git repository: {target_repo_path}")
        sys.exit(1)
    
    # Create temporary file for pytr output
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, dir=target_repo_path) as tmp_file:
        tmp_export_path = Path(tmp_file.name)
    
    try:
        # Run pytr export
        if not run_pytr_export(pytr_cmd, tmp_export_path):
            sys.exit(1)
        
        # Read existing master CSV and new export
        print_info(f"Reading existing master CSV: {csv_master_path}")
        existing_header, existing_rows = read_csv_rows(csv_master_path)
        print_info(f"Found {len(existing_rows)} existing transactions")
        
        print_info(f"Reading new export: {tmp_export_path}")
        new_header, new_rows = read_csv_rows(tmp_export_path)
        print_info(f"Found {len(new_rows)} transactions in export")
        
        # Determine header to use (prefer existing, fallback to new, then default)
        header = existing_header if existing_header else (new_header if new_header else FIELDNAMES)
        
        # Find new transactions
        new_transactions = find_new_transactions(existing_rows, new_rows)
        print_info(f"Detected {len(new_transactions)} new transactions")
        
        if not new_transactions:
            print_info("No new transactions detected. Nothing to commit.")
            return
        
        # Create backup if master CSV exists
        backup_path = None
        if csv_master_path.exists():
            backup_path = create_backup(csv_master_path, backup_dir)
            if backup_path:
                git_add_file(target_repo_path, backup_path)
        
        # Prepare updated CSV: preserve all existing rows, append new ones
        updated_rows = existing_rows + new_transactions
        
        # Write updated CSV
        print_info(f"Writing updated CSV with {len(updated_rows)} total transactions")
        if not write_csv_rows(csv_master_path, header, updated_rows):
            sys.exit(1)
        
        # Git operations
        print_info("Staging updated CSV file")
        if not git_add_file(target_repo_path, csv_master_path):
            sys.exit(1)
        
        # Create commit
        timestamp = datetime.now().strftime("%Y %m %d %H %M")
        commit_message = f"Update transactions {timestamp}"
        
        if not git_commit(target_repo_path, commit_message):
            print_info("No changes to commit (this should not happen if we detected new transactions)")
            return
        
        # Push to remote
        print_info(f"Pushing to origin/{git_branch}")
        if not git_push(target_repo_path, git_branch):
            sys.exit(1)
        
        print_info("✓ Transaction update completed successfully")
        
    finally:
        # Clean up temporary file
        if tmp_export_path.exists():
            try:
                tmp_export_path.unlink()
            except:
                pass


if __name__ == "__main__":
    main()
