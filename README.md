# TradeSync

**TradeSync** is a macOS application that automatically synchronizes your **Trade Republic** transactions to a **Google Drive** folder (CSV format).

It handles duplicates smartly, creates backups, and provides a simple user interface to manage the sync process, including 2FA handling.

![TradeSync Logo](logo.png)

## Features

- **Automated Export**: Connects to Trade Republic via `pytr` to fetch your transaction history.
- **Google Drive Sync**: Uploads new transactions to a master CSV file on Google Drive.
- **Smart Deduplication**: Merges new data with existing data, avoiding duplicates.
- **Backup System**: Automatically backs up the previous master file before updating.
- **User Interface**: A friendly local web interface to trigger syncs and view progress.
- **Durable**: Handles network errors and malformed data gracefully.

---

## 🚀 Installation & Usage

### 1. Download the App
Go to the `dist` folder and unzip `TradeSync.app.zip` (if available) or use the distributed executable.
*(Note: If you are building from source, see the Developer section below).*

### 2. Configuration
The first time you run **TradeSync**, you will need to set up your configuration. All config files are stored in `~/Library/Application Support/TradeSync` (on macOS).

You need:
1.  **Google OAuth Client ID**: A `credentials.json` file from Google Cloud Console (OAuth 2.0 Client ID for Desktop).
2.  **Trade Republic Config**: Your phone number and PIN.

### 3. Running the App
Double-click **TradeSync.app**.
A window will open showing the TradeSync interface. Click **"Sync Now"** to start.

- If prompted for 2FA (Trade Republic), check your phone and enter the code in the app.
- You will receive a macOS notification when the sync is complete.

---

## 👨‍💻 For Developers

This repository contains the source code for TradeSync.

### Requirements
- Python 3.11+
- Poetry or pip
- Google Cloud OAuth 2.0 Client credentials

### Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/tr_exporter.git
    cd tr_exporter
    ```

2.  **Install dependencies**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Run from Source**:
    You can run the application directly without compiling:
    ```bash
    python -m src.main  # Run valid CLI/Web logic
    # OR
    python -m src.launcher # Run the GUI wrapper
    ```

### Building the macOS App

We use **PyInstaller** to build the standalone `.app` bundle.

```bash
./scripts/build_release.sh
```

The output will be in `dist/TradeSync.app`.

### Project Structure

- `src/`: Source code.
    - `main.py`: Core CLI entry point.
    - `launcher.py`: GUI wrapper (pywebview).
    - `web.py`: FastAPI backend for the GUI.
    - `tr_handler.py`: Trade Republic integration logic.
    - `drive_client.py`: Google Drive API client.
    - `sync_logic.py`: Pandas logic for merging CSVs.
- `config/`: Configuration templates and schemas.
- `dist/`: Compiled application artifacts (Gitignored).

### Contributing

1.  Fork the repo.
2.  Create a feature branch.
3.  Commit your changes.
4.  Push to the branch.
5.  Create a Pull Request.

---

## License

MIT License. See `LICENSE` file for details.

**Disclaimer**: This is an unofficial tool and is not affiliated with Trade Republic. Use at your own risk.
