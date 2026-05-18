import pandas as pd
import os

def final_jira_sync():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    
    unmanaged_accounts = ['aws-fs-dev', 'aws-osttra-nft', 'aws-osttra-shared']
    linux_verified = ['portal-server', 'TestRail', 'lab-qa-auto', 'tra-starteam']
    
    xl = pd.ExcelFile(path)
    all_sheets = pd.read_excel(xl, sheet_name=None)
    
    for sn in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        if sn in all_sheets:
            df = all_sheets[sn]
            print(f"Applying final JIRA rules to: {sn}")
            
            # Rule 1: Unmanaged Accounts (Windows only)
            mask1 = (df['SUBSCRIPTION.Name'].isin(unmanaged_accounts)) & (df['VIRTUAL_MACHINE.operatingSystem'].astype(str).str.contains('Windows', case=False, na=False))
            df.loc[mask1, 'comment'] = "Windows Team dont manage this account & Dont have access too"
            
            # Rule 2: Client OS (NocAuto)
            mask2 = df['VIRTUAL_MACHINE.Name'].astype(str).str.contains('NocAuto', case=False, na=False)
            df.loc[mask2, 'comment'] = "Client OS Windows Team dont manage."
            
            # Rule 3: Linux Verified
            mask3 = df['VIRTUAL_MACHINE.Name'].isin(linux_verified)
            df.loc[mask3, 'comment'] = "Linux Server (Verified in SYSWIN-2378)"
            
            all_sheets[sn] = df

    print("Saving updated file...")
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        for name, sheet_df in all_sheets.items():
            sheet_df.to_excel(writer, sheet_name=name, index=False)
    print("Success! Final JIRA rules applied.")

if __name__ == "__main__":
    final_jira_sync()
