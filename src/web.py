import asyncio
import os
import sys
import pty
import fcntl
import struct
import termios
import logging
from fastapi import FastAPI, WebSocket, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.websockets import WebSocketDisconnect

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradeSyncWeb")

app = FastAPI()

# Determine base path for resources
# In PyInstaller, data files are extracted to sys._MEIPASS
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.getcwd()

# Mount static files with absolute path
app.mount("/static", StaticFiles(directory=os.path.join(base_path, "src/static")), name="static")

# Templates with absolute path
templates = Jinja2Templates(directory=os.path.join(base_path, "src/templates"))

from pydantic import BaseModel
from src.config_manager import ConfigManager

# Initialize ConfigManager with default system path
config_manager = ConfigManager()

class ConfigModel(BaseModel):
    drive_folder_id: str
    target_filename: str
    backup_enabled: bool
    backup_retention: int
    backup_folder_name: str
    notifications_enabled: bool
    phone_number: str = ""
    pin: str = ""

@app.get("/api/config")
async def get_config():
    cfg = config_manager.load_config()
    return {
        "drive_folder_id": cfg.get('drive', {}).get('folder_id', ''),
        "target_filename": cfg.get('drive', {}).get('target_filename', ''),
        "credentials_file": cfg.get('drive', {}).get('credentials_file') or cfg.get('drive', {}).get('service_account_file', 'credentials.json'),
        "backup_enabled": cfg.get('backup', {}).get('enabled', True),        "backup_retention": cfg.get('backup', {}).get('retention_count', 10),
        "backup_folder_name": cfg.get('backup', {}).get('folder_name', 'backups'),
        "notifications_enabled": cfg.get('notifications', {}).get('macos_enabled', True),
        "phone_number": cfg.get('credentials', {}).get('phone_number', ''),
        "pin": cfg.get('credentials', {}).get('pin', '')
    }

@app.post("/api/config")
async def update_config(data: ConfigModel):
    # Preserve existing credentials_file
    current_drive = config_manager.load_config().get('drive', {})
    existing_creds_file = current_drive.get('credentials_file') or current_drive.get('service_account_file', 'credentials.json')

    new_config = {
        'drive': {
            'folder_id': data.drive_folder_id,
            'target_filename': data.target_filename,
            'credentials_file': existing_creds_file
        },
        'backup': {
            'enabled': data.backup_enabled,
            'retention_count': data.backup_retention,
            'folder_name': data.backup_folder_name
        },
        'notifications': {
            'macos_enabled': data.notifications_enabled
        },
        'credentials': {
            'phone_number': data.phone_number,
            'pin': data.pin
        }
    }
    config_manager.update_config(new_config)
    return {"status": "success"}

from fastapi import UploadFile, File
import shutil

@app.post("/api/credentials")
async def upload_credentials(file: UploadFile = File(...)):
    if not file.filename.endswith('.json'):
        return {"status": "error", "message": "File must be a .json file"}
    
    # Save to config dir
    target_path = os.path.join(config_manager.config_dir, file.filename)
    try:
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Update config to point to this new file
        cfg = config_manager.load_config()
        if 'drive' not in cfg: cfg['drive'] = {}
        if 'service_account_file' in cfg['drive']:
            del cfg['drive']['service_account_file']
        cfg['drive']['credentials_file'] = file.filename
        config_manager.update_config(cfg)
        
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        logger.error(f"Failed to upload credentials: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws/sync")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Create a pseudo-terminal effectively
    # usage of PTY allows the subprocess to believe it has a real terminal, 
    # which is crucial for tools that behave differently in non-interactive shells (like getting 2FA codes)
    master_fd, slave_fd = pty.openpty()

    # Determine command based on whether we are frozen (executable) or running from source
    if getattr(sys, 'frozen', False):
        # Running as compiled app
        cmd = [sys.executable, "--worker"]
        # IMPORTANT: When double-clicked, CWD is often /. We must set it to a writable path
        # like the user's home or Documents, otherwise writing token.pickle will fail.
        # We'll use a specific subdir for cleanliness.
        work_dir = os.path.join(os.path.expanduser("~"), "Documents", "TradeSync_Data")
        os.makedirs(work_dir, exist_ok=True)
    else:
        # Running from source
        cmd = [sys.executable, "-m", "src.main"]
        work_dir = os.getcwd()

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=work_dir,
        preexec_fn=os.setsid # Create new session
    )

    os.close(slave_fd) # Close slave in parent so we get EOF when child closes it

    # Load credentials for Auto-Login
    cfg = config_manager.load_config()
    creds = cfg.get('credentials', {})
    auto_phone = creds.get('phone_number', '')
    auto_pin = creds.get('pin', '')
    
    # State tracking to avoid spamming inputs
    sent_phone = False
    sent_pin = False

    async def read_stdout():
        nonlocal sent_phone, sent_pin
        try:
            while True:
                # Read from the master fd
                # We use os.read directly because it's a file descriptor
                # We need to run this in a thread executor because os.read is blocking
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, os.read, master_fd, 1024)
                
                if not data:
                    break
                    
                # Decode bytes to string
                text = data.decode('utf-8', errors='replace')
                
                # === AUTO-LOGIN LOGIC (PTY Injection) ===
                if text:
                    text_lower = text.lower()
                    
                    # 1. Check for Phone Number Prompt
                    # Prompt: "Please enter your TradeRepublic phone number in the format +49..."
                    if not sent_phone and auto_phone and ("phone number" in text_lower or "format +" in text_lower):
                        logger.info("Auto-Login: Detected Phone Prompt. Injecting number...")
                        # Short delay to simulate typing/allow buffer flush
                        await asyncio.sleep(0.5) 
                        os.write(master_fd, (auto_phone + "\n").encode())
                        sent_phone = True
                        
                    # 2. Check for PIN Prompt
                    # Prompt could be "Please enter your PIN:", "PIN:", or just "Enter PIN"
                    # We check for "pin" if we haven't sent it yet.
                    # To avoid false positives, we check matches like "enter your pin", "pin:", "pin "
                    if not sent_pin and auto_pin and ("pin" in text_lower):
                         # Additional heuristic: usually happens AFTER phone logic or standalone
                         # We'll trust "pin" presence combined with typical prompt length or specific keywords
                         if any(x in text_lower for x in ["enter your pin", "pin:", "pin "]):
                            logger.info("Auto-Login: Detected PIN Prompt. Injecting PIN...")
                            await asyncio.sleep(0.5)
                            os.write(master_fd, (auto_pin + "\n").encode())
                            sent_pin = True
                
                # CENSOR PIN IN CONSOLE OUTPUT
                # If the PTY echoes the PIN, we mask it before sending to frontend.
                if auto_pin and len(auto_pin) >= 1:
                    text = text.replace(auto_pin, "*" * len(auto_pin))
                # ========================================

                await websocket.send_text(text)
        except OSError:
            pass # Process ended
        except Exception as e:
            logger.error(f"Error reading stdout: {e}")
        finally:
            await websocket.close()

    async def write_stdin():
        try:
            while True:
                data = await websocket.receive_text()
                # Write to master fd
                # encoding to bytes and writing to the PTY
                os.write(master_fd, data.encode())
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"Error writing stdin: {e}")

    # Run reader and writer concurrently
    try:
        await asyncio.gather(
            read_stdout(),
            write_stdin()
        )
    except Exception as e:
        logger.error("WebSocket connection closed or error occurred")
    finally:
        # Ensure process is terminated if WS closes
        if process.returncode is None:
            try:
                process.terminate()
                await process.wait()
            except ProcessLookupError:
                pass
        os.close(master_fd)
