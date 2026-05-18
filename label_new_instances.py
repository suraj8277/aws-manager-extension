import pandas as pd
import os

def mark_new_instances():
    april_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_29th Apr..xlsx'
    may_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    
    key_col = 'VIRTUAL_MACHINE.externalId'
    default_comment = 'New Instance - Not in April List'
    
    print("Loading April Master IDs...")
    april_df = pd.read_excel(april_path, sheet_name='Non-ASG Data')
    april_ids = set(april_df[key_col].astype(str).unique())
    
    # Identify the comment column name used previously (should be 'comment')
    potential_comment_cols = [col for col in april_df.columns if 'comment' in col.lower()]
    comment_col = potential_comment_cols[0] if potential_comment_cols else 'comment'

    print("Reading May file...")
    all_may_sheets = pd.read_excel(may_path, sheet_name=None)
    
    updated = False
    for sheet_name in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        if sheet_name in all_may_sheets:
            df = all_may_sheets[sheet_name]
            print(f"Checking for new instances in: {sheet_name}")
            
            # Identify rows where the ID is NOT in the April list
            # and the comment column is currently empty/NaN
            mask = (~df[key_col].astype(str).isin(april_ids))
            
            if comment_col not in df.columns:
                df[comment_col] = None
            
            # Fill only the ones that are missing/new
            df.loc[mask, comment_col] = df.loc[mask, comment_col].fillna(default_comment)
            
            all_may_sheets[sheet_name] = df
            updated = True
            
    if updated:
        print("Saving updated May file with labels...")
        with pd.ExcelWriter(may_path, engine='openpyxl') as writer:
            for name, sheet_df in all_may_sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        print("Success! New instances have been labeled.")

if __name__ == "__main__":
    mark_new_instances()
