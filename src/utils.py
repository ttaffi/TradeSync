import hashlib
import logging
import platform
import subprocess
import pandas as pd

logger = logging.getLogger(__name__)

def generate_row_hash(row) -> str:
    """
    Generate a SHA256 hash for a pandas Series (row).
    Concatenates all string representations of values.
    
    Args:
        row: A pandas Series representing a row.
        
    Returns:
        str: Hex digest of the hash.
    """
    # Normalize values for consistent hashing
    normalized_values = []
    for val in row.values:
        if pd.isna(val) or val == "":
            normalized_values.append("")
        elif isinstance(val, (int, float)):
            # Format numbers to avoid 6.890000001 mismatch
            # Check if it's essentially an integer
            if val == int(val):
                 normalized_values.append(str(int(val)))
            else:
                 normalized_values.append(f"{val:.2f}")
        else:
            # String: strip whitespace and quote marks that might be inconsistent
            # Also handle potential "nan" string literal
            s = str(val).strip()
            if s.lower() == 'nan':
                 normalized_values.append("")
            else:
                 normalized_values.append(s)

    row_str = "|".join(normalized_values)
    h = hashlib.sha256(row_str.encode('utf-8')).hexdigest()
    # logger.debug(f"Hashing: '{row_str}' -> {h}")
    return h

def send_macos_notification(title: str, message: str):
    """
    Send a native macOS desktop notification using AppleScript.
    
    Args:
        title (str): Notification title.
        message (str): Notification body.
    """
    if platform.system() != 'Darwin':
        logger.warning("Not running on macOS. Notification skipped.")
        return

    # Use NSUserNotification via Foundation for icon support
    try:
        from Foundation import NSUserNotification, NSUserNotificationCenter
        
        notification = NSUserNotification.alloc().init()
        notification.setTitle_(title)
        notification.setInformativeText_(message)
        # Sound
        notification.setSoundName_("NSUserNotificationDefaultSoundName")
        
        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        center.deliverNotification_(notification)
        
    except ImportError:
        # Fallback to osascript if PyObjC not present (though it should be)
        # Escape double quotes to prevent AppleScript syntax errors
        title = title.replace('"', '\\"')
        message = message.replace('"', '\\"')
        
        script = f'display notification "{message}" with title "{title}"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to send notification: {e}")
    except Exception as e:
         logger.error(f"Failed to send native notification: {e}")

