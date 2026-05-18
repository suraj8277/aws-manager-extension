import pandas as pd
import os

def sync_jira_status_to_excel():
    may_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    
    # Mapping based on Digamber's comment in SYSWIN-2378
    jira_status_map = {
        'portal-server': 'Linux Server (Verified in SYSWIN-2378)',
        'RDP servers': 'Windows Team dont manage this account & Dont have access too',
        'TestRail': 'Linux Server (Verified in SYSWIN-2378)',
        'lab-qa-auto': 'Linux Server (Verified in SYSWIN-2378)',
        'RDP servers Vikas': 'Windows Team dont manage this account & Dont have access too',
        'tra-starteam': 'Linux Server (Verified in SYSWIN-2378)',
        'JMETER - DO NOT TERMINATE !!!': 'Windows Team dont manage this account & Dont have access too',
        'Powerbi-review': 'Windows Team dont manage this account & Dont have access too',
        'tabular-powerbi-review': 'Windows Team dont manage this account & Dont have access too',
        'kpmg-sh01-review': 'Windows Team dont manage this account & Dont have access too',
        'kpmg-sh02-review': 'Windows Team dont manage this account & Dont have access too',
        'test-automation': 'Windows Team dont manage this account & Dont have access too',
        'osttra-ic-nft-windowsmq-server': 'Windows Team dont manage this account & Dont have access too',
        'PKI Testing windows': 'Windows Team dont manage this account & Dont have access too',
        'NocAuto': 'Client OS Windows Team dont manage.',
        # Handling the duplicate/variation found in Excel earlier
        'RDP servers Vikas': 'Windows Team dont manage this account & Dont have access too'
    }
    
    print("Reading May file...")
    all_sheets = pd.read_excel(may_path, sheet_name=None)
    
    updated_any = False
    for sheet_name in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        if sheet_name in all_sheets:
            df = all_sheets[sheet_name]
            print(f"Processing sheet: {sheet_name}")
            
            # Update based on Hostname match
            # We use a custom function to handle partial matches or variations if needed, 
            # but direct lookup is safer for now.
            for hostname, status in jira_status_map.items():
                mask = df['VIRTUAL_MACHINE.Name'].astype(str).str.contains(hostname, case=False, na=False)
                if mask.any():
                    df.loc[mask, 'comment'] = status
                    updated_any = True
            
            all_sheets[sheet_name] = df

    if updated_any:
        print("Saving updated May file with Jira statuses...")
        with pd.ExcelWriter(may_path, engine='openpyxl') as writer:
            for name, sheet_df in all_sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        print("Success! Jira statuses synced to Excel.")
    else:
        print("No matching hostnames found to update from Jira info.")

if __name__ == "__main__":
    sync_jira_status_to_excel()
