import os
import yaml
import logging
import argparse
import tempfile
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

# Rich Imports
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from src.config_manager import ConfigManager

# Configure logging (File logging only to keep stdout clean for Rich)
# We will intercept log messages if needed or rely on Rich for user output.
logging.basicConfig(
    level=logging.INFO,
    filename=os.path.expanduser("~/tradesync_error.log"),
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TradeSync")
console = Console()

def main() -> None:
    # Title
    console.print(Panel.fit("[bold white]TradeSync[/bold white] [green]CLI[/green]", border_style="green"))

    # Lazy imports with spinner
    with console.status("[bold green]Loading modules...[/bold green]", spinner="dots"):
        from src.drive_client import DriveClient
        from src.tr_handler import TradeRepublicHandler
        from src.sync_logic import SyncLogic
        from src.utils import send_macos_notification

    parser = argparse.ArgumentParser(description="TradeSync: Sync Trade Republic transactions to Google Drive.")
    parser.add_argument("--dry-run", action="store_true", help="Run without uploading changes to Drive.")
    parser.add_argument("--configure", action="store_true", help="Run the configuration wizard.")
    args = parser.parse_args()

    try:
        # --- Configuration Phase ---
        config_manager = ConfigManager()
        config_dir = config_manager.config_dir

        if args.configure:
            config_manager.run_wizard()
            return

        config = config_manager.load_config()
        
        # Check if config is missing or "unconfigured" (empty folder_id)
        # In Worker Mode (GUI), we DO NOT run the wizard here. The UI handles it.
        if not config or not config.get('drive', {}).get('folder_id'):
            console.print("CONFIG_MISSING: Please configure settings in the UI.")
            return

        # Load secrets
        load_dotenv(os.path.join(config_dir, '.env'))
        if os.getenv('DRIVE_FOLDER_ID'):
            config['drive']['folder_id'] = os.getenv('DRIVE_FOLDER_ID')

        # Resolve credentials path
        creds_file = config['drive'].get('credentials_file') or config['drive'].get('service_account_file')
        if not os.path.isabs(creds_file):
            creds_file = os.path.join(config_dir, creds_file)

        # CRITICAL: Verify credentials exist physically
        if not os.path.exists(creds_file):
             console.print(f"CREDENTIALS_MISSING: File not found at {creds_file}")
             return

        # NOTE: Drive Client initialization triggers Auth flow which might require user interaction (browser).
        # We suspend spinner for this.
        
        console.print("[dim]Authenticating with Google Drive...[/dim]")
        drive_client = DriveClient(creds_file)
        tr_handler = TradeRepublicHandler()
        sync_logic = SyncLogic()

        folder_id = config['drive']['folder_id']
        target_filename = config['drive']['target_filename']

        # --- Phase 1: Fetch Master File ---
        master_content: Optional[bytes] = None
        master_file_id: Optional[str] = None

        with console.status(f"[bold blue]Checking Drive for '{target_filename}'...[/bold blue]", spinner="earth"):
            master_file_id = drive_client.find_file(target_filename, folder_id)
            if master_file_id:
                console.print(f"[green]✔ Found master file (ID: {master_file_id})[/green]")
                master_content = drive_client.download_file(master_file_id)
            else:
                console.print("[yellow]⚠ No master file found. Creating new.[/yellow]")

        # --- Phase 2: Fetch Trade Republic Data ---
        console.print("[bold cyan]>>> syncing with Trade Republic...[/bold cyan]")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tr_handler.work_dir = temp_dir
            
            # This step involves interactive 2FA if not cached, or subprocess output.
            # We let it print to stdout/stderr.
            new_export_path = tr_handler.fetch_transactions("account_transactions.csv")
            
            if not new_export_path:
                console.print("[bold red]❌ Failed to fetch transactions from Trade Republic.[/bold red]")
                if config['notifications']['macos_enabled']:
                    send_macos_notification("TradeSync Failed", "Could not fetch data.")
                return

            # --- Phase 3: Processing ---
            processed_rows = None
            added_count = 0
            
            with console.status("[bold magenta]Processing and Merging Data...[/bold magenta]", spinner="arc"):
                processed_rows, added_count = sync_logic.process_and_merge(new_export_path, master_content)
                
            if added_count == 0:
                console.print("[bold green]✔ Sync completed. No new transactions.[/bold green]")
                if config['notifications']['macos_enabled']:
                    send_macos_notification("TradeSync", "No new transactions.")
                return
            
            # Save merged
            merged_output_path = os.path.join(temp_dir, "merged_master.csv")
            sync_logic.save_to_csv(processed_rows, merged_output_path)

            console.print(f"[bold green]✔ Added {added_count} new transactions![/bold green]")

            if args.dry_run:
                console.print("[bold yellow]DRY RUN: Skipping upload.[/bold yellow]")
                return

            # --- Phase 4: Parallel Upload (Backup + Master Update) ---
            console.print("[bold blue]>>> Syncing changes to Drive...[/bold blue]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                
                # Create Task IDs
                task_backup = progress.add_task("[dim]Backup ignored[/dim]", total=1, visible=False)
                task_update = progress.add_task("[cyan]Updating Master File...[/cyan]", total=1)
                
                jobs = []
                with ThreadPoolExecutor(max_workers=3) as executor:
                    
                    # 1. Update Master File Task
                    if master_file_id:
                        jobs.append(executor.submit(drive_client.update_file, master_file_id, merged_output_path))
                    else:
                        jobs.append(executor.submit(drive_client.upload_file, merged_output_path, folder_id, name=target_filename))
                    
                    # 2. Backup Task
                    if config['backup']['enabled'] and master_file_id and master_content:
                         # Prepare backup file
                         from datetime import datetime
                         timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                         backup_name = f"backup_{timestamp}_{target_filename}"
                         backup_path = os.path.join(temp_dir, backup_name)
                         with open(backup_path, 'wb') as f:
                             f.write(master_content)
                             
                         progress.update(task_backup, description=f"[blue]Uploading Backup: {backup_name}...[/blue]", visible=True)
                         
                         backup_folder_name = config['backup'].get('folder_name', 'backup')
                         
                         def do_backup_flow():
                             b_fid = drive_client.ensure_folder(backup_folder_name, folder_id)
                             drive_client.upload_file(backup_path, b_fid, name=backup_name)
                             drive_client.manage_backups(b_fid, "backup_", config['backup']['retention_count'])

                         jobs.append(executor.submit(do_backup_flow))

                    # Wait for all
                    for future in as_completed(jobs):
                        try:
                            future.result()
                            progress.advance(task_update) # Simple progress hack
                        except Exception as e:
                            console.print(f"[bold red]❌ Update Task Failed: {e}[/bold red]")
                            raise e

            # --- Final Summary ---
            table = Table(title="TradeSync Summary", show_header=True, header_style="bold magenta")
            table.add_column("Metric", style="dim")
            table.add_column("Value", style="bold")
            
            table.add_row("New Transactions", str(added_count))
            table.add_row("Total Transactions", str(len(processed_rows)))
            table.add_row("Status", "[green]Success[/green]")
            
            console.print(table)
            
            if config['notifications']['macos_enabled']:
                send_macos_notification("TradeSync Success", f"Synced {added_count} new transactions.")

    except Exception as e:
        console.print_exception(show_locals=False)
        if 'config' in locals() and config.get('notifications', {}).get('macos_enabled'):
            send_macos_notification("TradeSync Error", "An unexpected error occurred. Check logs.")

if __name__ == "__main__":
    main()
