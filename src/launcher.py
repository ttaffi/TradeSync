import sys
import os
import threading
import time
import socket
import webview

def get_free_port():
    """Ask the OS for a free ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def run_server(port):
    """Run the Uvicorn server (blocking)."""
    try:
        # Lazy imports
        import uvicorn
        from src.web import app
        # Run programmatically
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")
    except Exception as e:
        # Emergency logging
        log_file = os.path.join(os.path.expanduser("~"), "tradesync_error.log")
        with open(log_file, "a") as f:
            f.write(f"Server crash: {e}\n")
            import traceback
            traceback.print_exc(file=f)

def main():
    # 1. Worker Mode (Headless subprocess)
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        # Strip '--worker' so argparse in src.main doesn't choke on it
        sys.argv.pop(1) 
        from src.main import main as worker_main
        worker_main()
        return

    # 2. Launcher Mode (Native Window)
    
    # Select port
    port = get_free_port()
    
    # Start server in background thread
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    
    # Start server in background thread
    t = threading.Thread(target=run_server, args=(port,), daemon=True)
    t.start()
    
    # NO SLEEP here! We want the window instantly.
    # The polling loop handles the wait.
    
    # Create window with LOADING HTML
    # We start with a lightweight HTML page (Splash Screen) so user sees something INSTANTLY.
    
    LOADING_HTML = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradeSync</title>
    <style>
        :root { --bg-color: #f5f5f7; --card-bg: #ffffff; --text-primary: #1d1d1f; --text-secondary: #86868b; --font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
        body { background-color: var(--bg-color); color: var(--text-primary); font-family: var(--font-family); height: 100vh; display: flex; justify-content: center; align-items: center; margin: 0; }
        .container { width: 100%; max-width: 600px; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .logo { font-weight: 600; font-size: 24px; letter-spacing: -0.5px; color: #000; }
        .status-badge { font-size: 11px; font-weight: 500; padding: 4px 10px; border-radius: 20px; background-color: #e5e5ea; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; }
        .card { background-color: var(--card-bg); border-radius: 18px; border: 1px solid rgba(0, 0, 0, 0.05); overflow: hidden; margin-bottom: 24px; box-shadow: 0 4px 24px rgba(0, 0, 0, 0.04); height: 400px; display: flex; align-items: center; justify-content: center;}
        .actions { display: flex; justify-content: center; }
        .primary-btn { background-color: #000000; color: white; font-size: 15px; font-weight: 600; padding: 12px 36px; border-radius: 30px; border: none; opacity: 0.5; cursor: default; }
    </style>
    </head>
    <body>
        <div class="container">
            <header>
                <div class="header-left">
                    <div class="logo">TradeSync</div>
                    <div class="status-badge">Starting...</div>
                </div>
            </header>
            <main>
                <!-- Placeholder Card -->
                <div class="card">
                     <span style="color: #ccc; font-size: 14px;">Initializing...</span>
                </div>
                <div class="actions">
                    <button class="primary-btn">Sync Now</button>
                </div>
            </main>
        </div>
    </body>
    </html>
    """

    from src import __version__
    window = webview.create_window(
        f'TradeSync v{__version__}', 
        html=LOADING_HTML, # Load this immediately
        width=1000,
        height=700,
        min_size=(800, 600),
        resizable=True,
        js_api=JsApi()
    )
    
    def wait_for_server():
        # RUNS IN A THREAD
        target_url = f'http://localhost:{port}'
        retries = 50 
        for i in range(retries):
            try:
                # Check if port is open
                with socket.create_connection(("localhost", port), timeout=0.1):
                    pass
                
                # Check HTTP 200
                import urllib.request
                with urllib.request.urlopen(target_url, timeout=0.5) as response:
                     if response.status == 200:
                         # Server is ready.
                         # Safely update UI from thread
                         window.load_url(target_url)
                         return
            except Exception:
                time.sleep(0.1)
                
        # Fallback
        window.load_url(target_url)

    # Start the webview loop
    # We launch the poller in a standard thread instead of 'func' to avoid any start-up blocking
    t_poller = threading.Thread(target=wait_for_server, daemon=True)
    t_poller.start()
    
    webview.start(debug=False)
    
    # Cleanup
    os._exit(0)

class JsApi:
    """
    Python API exposed to JavaScript.
    Allows native file dialogs and direct config management.
    """
    def import_credentials(self):
        """
        Open native file dialog to select credentials.json, copy it to AppData, and update config.
        Returns: {status: 'success'|'cancel'|'error', filename: str, message: str}
        """
        try:
            # Open native dialog
            # Window 0 is the main window
            active_window = webview.windows[0]
            result = active_window.create_file_dialog(
                webview.OPEN_DIALOG, 
                directory='', 
                allow_multiple=False, 
                file_types=('JSON Files (*.json)', 'All files (*.*)')
            )
            
            if result and len(result) > 0:
                selected_path = result[0]
                filename = os.path.basename(selected_path)
                
                # Import here to avoid early import issues at module level
                import shutil
                import json
                from src.config_manager import ConfigManager
                
                # 1. VALIDATION
                auth_mode = "unknown"
                identifier = "Unknown"
                
                try:
                    with open(selected_path, 'r') as f:
                        data = json.load(f)
                        
                    if data.get('type') == 'service_account':
                         return {
                            "status": "error", 
                            "message": "Service Accounts are NOT supported. Please provide an OAuth 2.0 Client ID JSON."
                        }
                    elif 'installed' in data:
                         auth_mode = "oauth_installed"
                         identifier = "OAuth Desktop Client"
                    elif 'web' in data:
                         auth_mode = "oauth_web"
                         identifier = "OAuth Web Client"
                    else:
                        return {
                            "status": "error", 
                            "message": "Invalid file. Must be an OAuth 2.0 Client ID JSON (containing 'installed' or 'web')."
                        }
                    
                except json.JSONDecodeError:
                    return {"status": "error", "message": "Invalid JSON file."}
                except Exception as e:
                    return {"status": "error", "message": f"Validation failed: {e}"}

                # 2. COPY & UPDATE
                # Use ConfigManager to find target dir
                cm = ConfigManager()
                target_path = os.path.join(cm.config_dir, filename)
                
                # Copy file
                shutil.copy2(selected_path, target_path)
                
                # Update config
                cfg = cm.load_config()
                if 'drive' not in cfg: cfg['drive'] = {}
                if 'service_account_file' in cfg['drive']:
                    del cfg['drive']['service_account_file']
                cfg['drive']['credentials_file'] = filename
                cm.update_config(cfg)
                
                # CRITICAL: Delete existing token.pickle to force re-authentication with NEW file
                token_path = os.path.join(cm.config_dir, 'token.pickle')
                if os.path.exists(token_path):
                    try:
                        os.remove(token_path)
                    except Exception:
                        pass
                
                return {
                    "status": "success", 
                    "filename": filename,
                    "mode": auth_mode,
                    "identifier": identifier
                }
            else:
                return {"status": "cancel"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    main()
