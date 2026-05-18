import pandas as pd
import os

def sync_data():
    april_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_29th Apr..xlsx'
    may_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    
    # Common Key
    key_col = 'VIRTUAL_MACHINE.externalId'
    
    print("Reading April data (Non-ASG Data)...")
    april_df = pd.read_excel(april_path, sheet_name='Non-ASG Data')
    
    # Check for the comment column
    potential_comment_cols = [col for col in april_df.columns if 'comment' in col.lower()]
    if not potential_comment_cols:
        print("Warning: No 'comment' column found in April sheet. Available columns:", list(april_df.columns))
        return
    
    comment_col = potential_comment_cols[0]
    print(f"Using '{comment_col}' as the sync source.")

    # Create a mapping for updates
    sync_map = april_df.set_index(key_col)[comment_col].to_dict()

    print("Reading all sheets from May file...")
    all_may_sheets = pd.read_excel(may_path, sheet_name=None)
    
    updated_any = False
    for sheet_name in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        if sheet_name in all_may_sheets:
            df = all_may_sheets[sheet_name]
            print(f"Updating sheet: {sheet_name}")
            
            # Map the comment column based on Instance ID
            df[comment_col] = df[key_col].map(sync_map)
            all_may_sheets[sheet_name] = df
            updated_any = True
    
    if updated_any:
        print("Saving updated May file (all sheets preserved)...")
        with pd.ExcelWriter(may_path, engine='openpyxl') as writer:
            for name, sheet_df in all_may_sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        print("Success! May file updated with April comments.")
    else:
        print("No matching sheets found to update.")

if __name__ == "__main__":
    sync_data()
