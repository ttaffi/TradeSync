import logging
import io
import os
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

from src.utils import generate_row_hash

logger = logging.getLogger(__name__)

class SyncLogic:
    """
    Handles data processing, deduplication, and merging.
    """

    def __init__(self):
        # Specifics for Italian locale CSV from pytr
        self.csv_sep = ';'
        self.csv_decimal = ','
        self.encoding = 'utf-8' # or 'latin1' if needed, usually utf-8 for modern exports
        self.date_col = 'Data' # Based on user description "Data" column

    def load_data(self, file_path_or_buffer) -> 'pd.DataFrame':
        """
        Load CSV data into a Pandas DataFrame with correct locale settings.
        """
        import pandas as pd
        try:
            df = pd.read_csv(
                file_path_or_buffer, 
                sep=self.csv_sep, 
                decimal=self.csv_decimal,
                encoding=self.encoding
            )
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def process_and_merge(self, new_data_path: str, master_content: Optional[bytes] = None) -> Tuple['pd.DataFrame', int]:
        """
        Process the new export and merge it with the master dataset.
        
        Args:
            new_data_path (str): Path to the fresh pytr export.
            master_content (bytes, optional): Content of existing master file. None if clean start.
            
        Returns:
            Tuple[pd.DataFrame, int]: The merged DataFrame and the number of new rows added.
        """
        import pandas as pd
        logger.info("Loading new export data...")
        new_df = self.load_data(new_data_path)
        
        if master_content:
            logger.info("Loading existing master data...")
            master_df = self.load_data(io.BytesIO(master_content))
        else:
            logger.info("No existing master data found. Treating all new data as fresh.")
            master_df = pd.DataFrame(columns=new_df.columns)

        # Normalize DataFrames for consistent comparison
        # 1. Align Columns
        if not master_df.empty:
            # Ensure master has same columns as new (add missing as None, drop extras)
            # This ensures we are comparing apples to apples
            missing_in_master = set(new_df.columns) - set(master_df.columns)
            for c in missing_in_master:
                master_df[c] = None
            
            # Reorder master to match new_df
            master_df = master_df[new_df.columns]
        
        # 2. Type Normalization (Strict)
        # function to normalize a df in place
        def normalize_df(df):
            # DateTime
            if self.date_col in df.columns:
                try:
                    df[self.date_col] = pd.to_datetime(df[self.date_col], dayfirst=True)
                except Exception as e:
                    logger.warning(f"Date normalization failed: {e}")
            
            # Strings: Strip whitespace
            df_obj = df.select_dtypes(['object'])
            df[df_obj.columns] = df_obj.apply(lambda x: x.str.strip())
            
            # Floats (Italian locale handling if still strings)
            # Try to convert known numeric columns like 'Importo', 'Saldo'
            for col in ['Importo', 'Saldo', 'Amount']:
                if col in df.columns and df[col].dtype == 'object':
                    try:
                        # Replace ',' with '.' and convert to float
                        df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False).replace('nan', '0')
                        df[col] = pd.to_numeric(df[col])
                    except:
                        pass
            return df

        new_df = normalize_df(new_df)
        if not master_df.empty:
            master_df = normalize_df(master_df)

        # 3. Native Deduplication
        # We concatenate Master + New
        # Then drop duplicates, keeping the 'first' occurrence (which is Master's if it exists)
        # This implicitly handles the intersection.
        
        initial_len = len(master_df)
        
        # Use a "combined" fallback if master is empty
        if master_df.empty:
             merged_df = new_df.drop_duplicates()
             added_count = len(merged_df)
        else:
            # Concat
            combined_df = pd.concat([master_df, new_df], ignore_index=True)
            
            # Drop Duplicates
            # subset=None means use all columns
            merged_df = combined_df.drop_duplicates(keep='first')
            
            final_len = len(merged_df)
            added_count = final_len - initial_len

        if added_count > 0:
            logger.info(f"Merged {added_count} new unique transactions via Pandas Deduplication.")
        else:
            logger.info("No new unique transactions found.")
            
        # 4. Final Formatting for Export (Sort by Date)
        if self.date_col in merged_df.columns:
            try:
                # Ensure it's datetime for sorting
                if not pd.api.types.is_datetime64_any_dtype(merged_df[self.date_col]):
                     merged_df[self.date_col] = pd.to_datetime(merged_df[self.date_col], dayfirst=True)
                     
                merged_df = merged_df.sort_values(by=self.date_col, ascending=False)
                
                # Convert back to native string format for CSV (optional, but good for CSV 'pretty' look)
                # Or just leave as objects, to_csv handles it. 
                # But to maintain input format "YYYY-MM-DD HH:MM:SS" we might want to format.
                # Let's verify what the original format was. 
                # User liked "YYYY-MM-DD HH:MM:SS".
                # merged_df[self.date_col] = merged_df[self.date_col].dt.strftime('%Y-%m-%d %H:%M:%S')
                pass 
            except Exception as e:
                logger.warning(f"Sorting failed: {e}")

        return merged_df, added_count
    
    def save_to_csv(self, df: 'pd.DataFrame', path: str):
         # If existing file used specific formatting, we should try to respect it.
         # But preventing future dupes requires STANDARD output.
         # We force standard numeric/date formats.
         
         import pandas as pd
         # Format Date col as string if it is datetime
         save_df = df.copy()
         if self.date_col in save_df.columns and pd.api.types.is_datetime64_any_dtype(save_df[self.date_col]):
             save_df[self.date_col] = save_df[self.date_col].dt.strftime('%Y-%m-%d %H:%M:%S')

         save_df.to_csv(path, sep=self.csv_sep, decimal=self.csv_decimal, index=False, encoding=self.encoding)
