import logging
import io
import os
import csv
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

from src.utils import generate_row_hash

logger = logging.getLogger(__name__)

class SyncLogic:
    """
    Handles data processing, deduplication, and merging using native Python CSV/JSON.
    """

    def __init__(self):
        # Specifics for Italian locale CSV from pytr
        self.csv_sep = ';'
        self.csv_decimal = ','
        self.encoding = 'utf-8' 
        self.date_col = 'Data' # Key column for sorting

    def load_data(self, file_path_or_buffer) -> List[Dict[str, str]]:
        """
        Load CSV data into a list of dictionaries.
        """
        try:
            # Check if it's a file path or a buffer
            if isinstance(file_path_or_buffer, str):
                f = open(file_path_or_buffer, 'r', encoding=self.encoding, newline='')
                should_close = True
            else:
                # Assume buffer (BytesIO or TextIOWrapper)
                # If BytesIO, need to wrap in TextIOWrapper for csv module
                if isinstance(file_path_or_buffer, io.BytesIO):
                     f = io.TextIOWrapper(file_path_or_buffer, encoding=self.encoding, newline='')
                else:
                     f = file_path_or_buffer
                should_close = False
            
            try:
                reader = csv.DictReader(f, delimiter=self.csv_sep)
                data = list(reader)
                return data
            finally:
                if should_close:
                    f.close()

        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def process_and_merge(self, new_data_path: str, master_content: Optional[bytes] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        Process the new export and merge it with the master dataset.
        
        Args:
            new_data_path (str): Path to the fresh pytr export.
            master_content (bytes, optional): Content of existing master file. None if clean start.
            
        Returns:
            Tuple[List[Dict], int]: The merged list of rows and the number of new rows added.
        """
        logger.info("Loading new export data...")
        new_rows = self.load_data(new_data_path)
        
        master_rows = []
        if master_content:
            logger.info("Loading existing master data...")
            master_rows = self.load_data(io.BytesIO(master_content))
        else:
            logger.info("No existing master data found. Treating all new data as fresh.")

        # 2. Normalization Function
        def normalize_row(row: Dict[str, str]) -> Dict[str, Any]:
            norm = row.copy()
            # String strip
            for k, v in norm.items():
                if isinstance(v, str):
                    norm[k] = v.strip()
            
            # Float Normalization (Italian Locale)
            # Try to convert known numeric columns to standard float strings or keep as is?
            # Actually, keeping them as strings is fine for storage, but for "deduplication" 
            # we need consistency. 
            # Let's clean the string representation: "1.000,00" -> "1000.00"
            for col in ['Importo', 'Saldo', 'Amount']:
                if col in norm and norm[col]:
                    val = norm[col]
                    if isinstance(val, str):
                        # Remove dots (thousands), replace comma with dot
                        clean_val = val.replace('.', '').replace(',', '.')
                        # Just update the string in place to be "standard numeric"
                        try:
                            # Verify if it floats
                            float(clean_val)
                            norm[col] = clean_val
                        except ValueError:
                            pass # Not a number, leave as is
            return norm

        # Normalize specific columns if needed (mostly for hashing consistency)
        normalized_new = [normalize_row(r) for r in new_rows]
        normalized_master = [normalize_row(r) for r in master_rows]

        # 3. Deduplication
        # Strategy: Build a set of hashes from MASTER.
        # Iterate NEW. If hash not in set, add to MASTER.
        
        # NOTE: This assumes Master is the source of truth.
        # If new export has "updated" data for same row, this logic ignores it (keeps master).
        # This matches "drop_duplicates(keep='first')" behavior if we prepend master.
        
        existing_hashes = set()
        for row in normalized_master:
            h = generate_row_hash(row)
            existing_hashes.add(h)
            
        initial_count = len(normalized_master)
        
        merged_rows = list(normalized_master) # Start with master
        added_count = 0
        
        for row in normalized_new:
            h = generate_row_hash(row)
            if h not in existing_hashes:
                merged_rows.append(row)
                existing_hashes.add(h)
                added_count += 1
                
        if added_count > 0:
            logger.info(f"Merged {added_count} new unique transactions.")
        else:
            logger.info("No new unique transactions found.")
            
        # 4. Sorting
        if merged_rows and self.date_col in merged_rows[0]:
            try:
                def parse_date(row):
                    d_str = row.get(self.date_col, "")
                    # Try explicit formats
                    # Input is usually YYYY-MM-DD or DD.MM.YYYY
                    if not d_str: return datetime.min
                    
                    formats = ['%Y-%m-%d', '%d.%m.%Y', '%Y-%m-%d %H:%M:%S']
                    for fmt in formats:
                        try:
                            return datetime.strptime(d_str, fmt)
                        except ValueError:
                            continue
                    return datetime.min

                merged_rows.sort(key=parse_date, reverse=True)
            except Exception as e:
                logger.warning(f"Sorting failed: {e}")

        return merged_rows, added_count
    
    def save_to_csv(self, rows: List[Dict[str, Any]], path: str):
         if not rows:
             logger.warning("No rows to save.")
             return

         try:
             # Extract headers from the first row (or union of all keys if sparse?)
             # Usually CSVs have uniform keys. Use first row logic or master keys.
             fieldnames = list(rows[0].keys())
             
             with open(path, 'w', encoding=self.encoding, newline='') as f:
                 writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=self.csv_sep)
                 writer.writeheader()
                 
                 # Formatting hook before write?
                 # If we normalized floats to "1000.00" (dot decimal), 
                 # but we want output in Italian "1000,00" (comma decimal)?
                 # The user settings define self.csv_decimal = ','
                 # If we changed them in normalization, we might want to revert for display/consistency?
                 # Or we just save the normalized "standard" version?
                 # The previous Pandas implementation respected `decimal=','` on SAVE.
                 # So pandas converted floats to "1,00" string on write.
                 # We must do the same manually.
                 
                 for row in rows:
                     row_to_write = row.copy()
                     # Re-localize floats
                     for col in ['Importo', 'Saldo', 'Amount']:
                         if col in row_to_write:
                             val = row_to_write[col]
                             if isinstance(val, str) and '.' in val and ',' not in val:
                                 # It looks like a standard float string "1234.56"
                                 # Convert to "1234,56"
                                 row_to_write[col] = val.replace('.', ',')
                     writer.writerow(row_to_write)
                     
         except Exception as e:
             logger.error(f"Failed to save CSV: {e}")
             raise
