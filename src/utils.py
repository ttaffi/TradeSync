import hashlib
import logging
import platform
import subprocess

logger = logging.getLogger(__name__)

def generate_row_hash(row: dict) -> str:
    """
    Generate a SHA256 hash for a dictionary row.
    Concatenates all string representations of values.
    
    Args:
        row: A dictionary representing a row (keys are columns, values are data).
        
    Returns:
        str: Hex digest of the hash.
    """
    # Normalize values for consistent hashing
    normalized_values = []
    
    # Sort keys to ensure consistent order if row is a dict
    # (though csv.DictReader preserves order in modern Python, sorting allows column reordering to not affect row identity if we wanted, 
    # but strictly speaking, if columns change order, it's a diff schema. 
    # Let's assume we iterate over values in the order they appear if it's an OrderedDict or just values if we pass a list.
    # But wait, the caller might pass a dict. Let's use row.values() for simplicity if we trust order, 
    # OR better: the caller should probably safeguard column order.
    # However, for deduplication, we usually care about the DATA content. 
    # Let's trust the caller passes a dict with consistent keys or values.
    
    # Actually, previous implementation used row.values (pandas Series).
    # If we switch to dicts, row.values() works.
    
    for val in row.values():
        s_val = str(val) if val is not None else ""
        
        if val is None or s_val == "":
            normalized_values.append("")
        else:
            # Check for numbers manually?
            # Pandas did `isinstance(val, (int, float))`.
            # In CSV reading (without pandas), everything is a STRING initially.
            # So `val` will likely be "123" or "123.45" or "10,50".
            
            # If we want to mimic the previous float logic "6.890000001", 
            # we need to know if it's a number.
            # But since we are reading from CSV as strings, we might just hash the string representation 
            # IF we normalize it first.
            # The previous logic had:
            # if isinstance(val, (int, float)): ...
            # else: string processing
            
            # Since we are moving to pure CSV reading, we might not have floats yet unless we converted them.
            # Let's be robust: strip whitespace.
            
            s = s_val.strip()
            if s.lower() == 'nan':
                normalized_values.append("")
            else:
                normalized_values.append(s)

    row_str = "|".join(normalized_values)
    h = hashlib.sha256(row_str.encode('utf-8')).hexdigest()
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

