<div align="center">
  <img src="logo.png" alt="TradeSync Logo" width="180"/>
  <h1>TradeSync</h1>
  <p>
    <strong>Automated Transaction Synchronization for Trade Republic</strong>
  </p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
  [![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
  [![Platform macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://www.apple.com/macos/)
  [![Release](https://img.shields.io/github/v/release/ttaffi/TradeSync)](https://github.com/ttaffi/TradeSync/releases)

  <p>
    Seamlessly export your Trade Republic transactions and keep your Google Drive spreadsheet in sync.
    <br/>
    Built for macOS. Secure, local, and automated.
  </p>
</div>

---

## 📖 Overview

**TradeSync** resolves the pain of manually exporting and tracking your portfolio changes. It acts as a bridge between your Trade Republic account and your personal finance spreadsheets on Google Drive.

By automating the retrieval (`pytr`) and synchronization (`Google Drive API`) of data, TradeSync ensures your financial records are always up-to-date without duplicates or manual intervention.

## ✨ Key Features

-   **🔄 Automated Sync**: One-click synchronization of your entire transaction history.
-   **☁️ Google Drive Integration**: Directly appends new transactions to your chosen CSV file in the cloud.
-   **🧠 Smart Deduplication**: Intelligently hashing rows to prevent duplicates, even if you sync multiple times.
-   **🛡️ Safety First**:
    -   **Local Processing**: Your credentials stay on your machine.
    -   **Auto-Backup**: Automatically creates a timestamped backup of your remote CSV before every update.
-   **🖥️ Native macOS Experience**:
    -   Standalone `.app` (no Python required).
    -   Native notifications on completion.
    -   Sleek, modern UI with Dark Mode support.

---

## 🚀 Getting Started

### Prerequisites

1.  **Trade Republic Account**: A verified phone number and PIN.
2.  **Google Account**: Creating a project in Google Cloud Console (see [Configuration](#-configuration)).

### Installation

1.  Go to the [Releases](https://github.com/ttaffi/TradeSync/releases) page.
2.  Download the latest `TradeSync.dmg`.
3.  Open the DMG and drag **TradeSync.app** to your `Applications` folder.

### Usage

1.  Launch **TradeSync** from your Applications.
2.  The first time you run it, you'll be guided through the [Configuration](#-configuration) setup.
3.  Once configured, simply click **Sync Now**.
    -   If 2FA is required, the app will prompt you for the code sent to your phone.
    -   Sit back and wait for the "Sync Complete" notification!

---

## ⚙️ Configuration

To ensure security, TradeSync requires your own credentials. It does not use a shared server.

### 1. Google Cloud Credentials
You need to generate a `credentials.json` file to allow TradeSync to access your Google Drive.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new Project (e.g., "TradeSync Personal").
3.  Enable the **Google Drive API** for this project.
4.  Go to **APIs & Services > OAuth consent screen**.
    -   User Type: **External** (unless you have a Workspace org).
    -   Fill in required fields (AppName, email).
    -   **Test Users**: Add your own Google email address.
5.  Go to **Credentials > Create Credentials > OAuth client ID**.
    -   Application type: **Desktop app**.
6.  Download the JSON file and rename it to `credentials.json`.
7.  **Import this file** when prompted by TradeSync settings.

### 2. Google Drive Folder
1.  Create a folder in your Google Drive where you want the transactions to be saved.
2.  Copy the **Folder ID** from the URL (the string after `folders/` in your browser address bar).
3.  Paste this ID into TradeSync settings.

### 3. Trade Republic
-   **Phone Number**: International format (e.g., `+393331234567`).
-   **PIN**: Your 4-digit app PIN.

---

## 👨‍💻 Development

Want to contribute? Setup your local environment to build and test TradeSync.

### Requirements
-   Python 3.11+
-   `virtualenv`

### Setup

```bash
# Clone the repository
git clone https://github.com/ttaffi/TradeSync.git
cd TradeSync

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

```bash
# Run the GUI Application
python -m src.launcher

# Run Core Logic (CLI)
python -m src.main
```

### Building for Release

We use `PyInstaller` to create the standalone macOS application.

```bash
./scripts/build_release.sh
```
Artifacts will be generated in `dist/`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">
  <p><i>Note: This is an unofficial tool and is not affiliated with Trade Republic Bank GmbH. Use at your own risk.</i></p>
</div>
