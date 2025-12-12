import os
import logging
import sys
import asyncio
from pathlib import Path
from typing import Optional

# Import pytr modules directly
# Moved to fetch_transactions for lazy loading

class TradeRepublicHandler:
    """
    Handles interactions with Trade Republic via the pytr library.
    Invokes pytr classes directly to ensure robust control over execution and output.
    """

    def __init__(self, work_dir: str = ".") -> None:
        self.work_dir = work_dir
        self.logger = logging.getLogger(__name__)

        # SILENCE EXTERNAL LOGGERS
        # pytr uses 'coloredlogs' which can be noisy. We raise the level to WARN/ERROR.
        logging.getLogger("pytr").setLevel(logging.WARNING)
        logging.getLogger("websockets").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    def fetch_transactions(self, output_filename: str = "account_transactions.csv") -> Optional[str]:
        """
        Execute pytr to export transactions via direct API calls.
        Redirects user interaction (2FA) through standard IO.
        
        Args:
            output_filename (str): Expected output filename.
            
        Returns:
            Optional[str]: Path to the generated CSV file, or None if failed.
        """
        output_path = Path(self.work_dir).resolve()
        
        # DEBUG LOGGING SETUP
        # Use an absolute path for the debug log (user home) so it isn't deleted with temp dirs
        debug_file = os.path.expanduser("~/debug_tr_handler.log")
        
        def log_debug(msg):
             print(f"DEBUG: {msg}") # ALSO PRINT TO STDOUT so user sees it immediately
             try:
                 with open(debug_file, "a") as f:
                     f.write(f"{msg}\n")
             except Exception:
                 pass # Ignore logging errors

        # Start log for this run
        try:
            with open(debug_file, "a") as f:
                f.write(f"\n--- New Run (Direct API) ---\nWork dir: {output_path}\n")
        except Exception:
            pass

        self.logger.info("Starting Trade Republic export...")
        print("\n\033[1;33m>>> Launching pytr. Please follow the instructions on screen (2FA). <<<\033[0m\n")

        try:
             # Lazy imports to speed up app startup
            import pytr.account
            import pytr.timeline
            import pytr.transactions
            import pytr.event
            
            # 1. Login
            log_debug("Logging in interactively...")
            
            # FORCE FRESH SESSION (User Request)
            # Delete ~/.pytr to ensure we are prompted for 2FA every time.
            # web.py will auto-fill Phone and PIN, user does 2FA.
            pytr_dir = Path.home() / ".pytr"
            if pytr_dir.exists():
                import shutil
                try:
                    shutil.rmtree(pytr_dir)
                    log_debug("Cleaned up existing session to force fresh login.")
                except Exception as e:
                    self.logger.warning(f"Could not clear session: {e}")

            # Enable pytr logging for better debugging (temporary)
            logging.getLogger("pytr").setLevel(logging.DEBUG)

            try:
                # We set store_credentials=True to behave like a persistent CLI
                tr = pytr.account.login(store_credentials=True) 
                log_debug("Login successful.")
            except Exception as e:
                self.logger.warning(f"Login failed: {e}. Attempting to reset credentials and retry...")
                log_debug(f"Login failed ({e}). Resetting ~/.pytr ...")
                
                # Check for and clear ~/.pytr
                pytr_dir = Path.home() / ".pytr"
                if pytr_dir.exists():
                    import shutil
                    try:
                        shutil.rmtree(pytr_dir)
                        log_debug("Deleted ~/.pytr directory.")
                    except Exception as rm_err:
                        log_debug(f"Failed to delete .pytr: {rm_err}")
                
                # Undo any partial login state if possible (though shutil.rmtree should handle the files)
                print("\n\033[1;31mLogin failed (Session invalid). Retrying with fresh login...\033[0m\n")
                
                # Retry
                tr = pytr.account.login(store_credentials=True)
                log_debug("Retry login successful.")

            # 2. Initialize Timeline
            # Timeline expects a Path object for output_path
            log_debug(f"Initializing Timeline with output_path={output_path}")
            tl = pytr.timeline.Timeline(tr, output_path)
            
            # 3. Run Timeline Loop
            log_debug("Starting timeline loop...")
            asyncio.run(tl.tl_loop())
            log_debug(f"Timeline loop finished. Events collected: {len(tl.events)}")

            # 4. Export Transactions
            events = tl.events
            export_path = output_path / output_filename
            
            log_debug(f"Exporting to {export_path}")
            
            # Parse events one by one to handle malformed data
            parsed_events = []
            for item in events:
                try:
                    parsed_events.append(pytr.event.Event.from_dict(item))
                except Exception as e:
                    # Log the failing event but continue
                    title = item.get('title', 'Unknown')
                    subtitle = item.get('subtitle', 'Unknown')
                    error_msg = f"Skipping malformed event {item.get('id')} ({title} - {subtitle}): {e}"
                    print(f"WARNING: {error_msg}")
                    log_debug(f"WARNING: {error_msg}")
                    # Optional: Log the full item structure to debug log
                    log_debug(f"Malformed item structure: {item}")

            if not parsed_events:
                 self.logger.error("No events could be parsed successfully.")
                 log_debug("FAILURE: No events parsed.")
                 return None

            with open(export_path, "w", encoding="utf-8") as f:
                # Assuming 'en' and 'csv' based on typical usage
                pytr.transactions.TransactionExporter("en").export(
                    f, 
                    parsed_events, 
                    "csv"
                )
            
            if export_path.exists():
                self.logger.info("pytr export completed successfully.")
                log_debug(f"SUCCESS: File created at {export_path}")
                return str(export_path)
            else:
                 self.logger.error(f"pytr finished but file {output_filename} was not found.")
                 log_debug("FAILURE: Export finished but file missing.")
                 return None

        except ImportError:
            self.logger.error("Could not import pytr. Is it installed?")
            log_debug("ImportError - is pytr installed?")
            return None
        except Exception as e:
            self.logger.exception(f"Unexpected error during pytr export: {e}")
            log_debug(f"EXCEPTION: {e}")
            import traceback
            try:
                with open(debug_file, "a") as f:
                    traceback.print_exc(file=f)
            except Exception:
                traceback.print_exc()
            return None
