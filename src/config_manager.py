import os
import yaml
import logging
import platform
from typing import Dict, Any
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

class ConfigManager:
    """
    Manages configuration loading and user data directory.
    Standardizes on ~/Library/Application Support/TradeSync for macOS.
    """

    def __init__(self, config_dir: str = None):
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = self.get_app_data_dir()
        
        self.config_path = os.path.join(self.config_dir, 'config.yaml')
        self.env_path = os.path.join(self.config_dir, '.env')
        self.logger = logging.getLogger(__name__)
        
        # Ensure directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        self._ensure_defaults()

    @staticmethod
    def get_app_data_dir() -> str:
        """
        Returns the platform-specific application data directory.
        On macOS: ~/Library/Application Support/TradeSync
        """
        home = os.path.expanduser("~")
        if platform.system() == "Darwin":
             return os.path.join(home, "Library", "Application Support", "TradeSync")
        else:
             # Fallback for Linux/Windows dev
             return os.path.join(home, ".tradesync")

    def _ensure_defaults(self):
        """
        If config.yaml doesn't exist in AppData, copy the one bundled with the app/script.
        """
        if not os.path.exists(self.config_path):
            self.logger.info(f"No config found at {self.config_path}. Copying defaults...")
            
            # Determine source path checking for PyInstaller bundle
            import sys
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
                source_config = os.path.join(base_path, 'config', 'config.yaml')
            else:
                # Dev mode: assumes we are in src/config_manager.py -> ../config
                source_config = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
            
            if os.path.exists(source_config):
                try:
                    with open(source_config, 'r') as src, open(self.config_path, 'w') as dst:
                        dst.write(src.read())
                    self.logger.info("Default config copied successfully.")
                except Exception as e:
                    self.logger.error(f"Failed to copy default config: {e}")
            else:
                self.logger.warning(f"Source config not found at {source_config}")

    def load_config(self) -> Dict[str, Any]:
        """
        Load config if exists.
        Returns empty dict if not found.
        """
        if not os.path.exists(self.config_path):
            return {}
        
        with open(self.config_path, 'r') as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError:
                return {}

    def update_config(self, new_config: Dict[str, Any]):
        """
        Update configuration file with new values.
        """
        # Ensure dir exists again just in case
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False)

    def run_wizard(self):
        """
        Run interactive setup wizard to populate config.
        """
        print("\n\033[1;36m=== TradeSync Setup Wizard ===\033[0m\n")
        print("Welcome! Let's configure your TradeSync environment.")
        print("We will create 'config/config.yaml' and 'config/.env' for you.\n")

        # Load existing values as defaults
        current_config = self.load_config()
        current_drive = current_config.get('drive', {})
        current_backup = current_config.get('backup', {})
        current_notif = current_config.get('notifications', {})

        # Google Drive Config
        print("\033[1;33m--- Google Drive Configuration ---\033[0m")
        print("To connect to Google Drive, we need your 'credentials.json' file (Service Account or OAuth Client).")
        print("If you haven't created one, please do so in the Google Cloud Console.\n")

        # 1. Credentials File
        while True:
            target_creds_path = os.path.join(self.config_dir, 'credentials.json')
            
            # Check if one already exists in config dir
            if os.path.exists(target_creds_path):
                use_existing = inquirer.confirm(
                    message=f"Found existing 'credentials.json' in {self.config_dir}. Use it?",
                    default=True
                ).execute()
                if use_existing:
                    break
            
            # Ask user to locate it
            src_creds_path = inquirer.filepath(
                message="Select your 'credentials.json' file:",
                default=os.getcwd(), # Start in current dir
                validate=lambda path: os.path.isfile(path) and path.endswith('.json'),
                only_files=True
            ).execute()

            if src_creds_path:
                try:
                    # Copy to config dir
                    import shutil
                    shutil.copy2(src_creds_path, target_creds_path)
                    print(f"✔ Copied credentials to {target_creds_path}")
                    break
                except Exception as e:
                    print(f"❌ Failed to copy file: {e}. Please try again.")
            else:
                 # User cancelled or empty?
                 print("You must provide a credentials file to proceed.")

        # 2. Folder ID
        folder_id = inquirer.text(
            message="Enter your Google Drive Folder ID:",
            instruction="(The alphanumeric ID in your Drive folder URL)",
            validate=lambda x: len(x.strip()) > 5, # Basic validation
            invalid_message="ID seems too short",
        ).execute()

        # 3. Target Filename
        target_file = inquirer.text(
            message="Name of the master CSV file on Drive:",
            default='Ledger_Trade_Republic.csv',
            instruction="(This file will be created if it doesn't exist)"
        ).execute()

        # Backup Config
        print("\n\033[1;33m--- Backup Configuration ---\033[0m")
        enable_backup = inquirer.confirm(
            message="Enable automatic backups?",
            default=current_backup.get('enabled', True)
        ).execute()
        
        retention = 10
        if enable_backup:
            retention = inquirer.number(
                message="How many backups to keep?",
                default=current_backup.get('retention_count', 10),
                min_allowed=1
            ).execute()

        # Notifications
        print("\n\033[1;33m--- Notification Configuration ---\033[0m")
        enable_notif = inquirer.confirm(
            message="Enable macOS Desktop Notifications?",
            default=current_notif.get('macos_enabled', True)
        ).execute()

        # Construct payload
        new_config = {
            'drive': {
                'folder_id': folder_id.strip(),
                'target_filename': target_file.strip(),
                'credentials_file': 'credentials.json'
            },
            'backup': {
                'enabled': enable_backup,
                'retention_count': int(retention),
                'folder_name': 'backups'
            },
            'notifications': {
                'macos_enabled': enable_notif
            }
        }

        # Save to file
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False)
        
        # Also create empty .env if not exists, just to be safe, though we put everything in config.yaml now for simplicity of this wizard.
        # The user's request emphasized "automatic setting of settings".
        if not os.path.exists(self.env_path):
            with open(self.env_path, 'w') as f:
                f.write("# Secrets (Managed by TradeSync Setup)\n")

        print(f"\n\033[1;32mConfiguration saved to {self.config_path}!\033[0m\n")
