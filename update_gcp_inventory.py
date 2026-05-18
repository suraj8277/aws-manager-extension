import pandas as pd
import os

def update_gcp_sheet():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    sheet_name = 'Detail3-GCP'
    
    tanium_path = "/opt/Tanium/TaniumClient"
    cortex_path = "/opt/traps"
    comment_note = "Investigating missing agents - Ref GCP-1407"
    
    print(f"Reading file to update sheet: {sheet_name}...")
    all_sheets = pd.read_excel(path, sheet_name=None)
    
    if sheet_name in all_sheets:
        df = all_sheets[sheet_name]
        
        # Add new columns
        df['Tanium_Path'] = tanium_path
        df['Cortex_Path'] = cortex_path
        df['comment'] = comment_note
        
        all_sheets[sheet_name] = df
        print(f"Added paths and comments to {len(df)} rows.")
        
        print("Saving updated file...")
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            for name, sheet_df in all_sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        print("Success! Detail3-GCP updated.")
    else:
        print(f"Error: Sheet '{sheet_name}' not found.")

if __name__ == "__main__":
    update_gcp_sheet()
