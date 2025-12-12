import logging
import pytr.account
from pathlib import Path

def main():
    print("--- TradeSync Debug Login Script ---")
    print("This script runs pytr login directly to verify connectivity.")
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        print("Attempting login...")
        tr = pytr.account.login(store_credentials=True)
        print("\nSUCCESS: Login completed successfully!")
        print("You can close this script.")
    except Exception as e:
        print(f"\nFAILURE: Login failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
