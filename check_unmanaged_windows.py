import pandas as pd

def find_unmanaged_windows():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    accounts = ['aws-fs-dev', 'aws-osttra-nft', 'aws-osttra-shared']
    
    xl = pd.ExcelFile(path)
    for sn in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        df = pd.read_excel(xl, sheet_name=sn)
        print(f"\n--- {sn} ---")
        
        # Filter for Windows servers in the specific accounts
        mask = (df['SUBSCRIPTION.Name'].isin(accounts)) & (df['VIRTUAL_MACHINE.operatingSystem'].astype(str).str.contains('Windows', case=False, na=False))
        
        matches = df[mask]
        if not matches.empty:
            for _, row in matches.iterrows():
                print(f"Hostname: {row['VIRTUAL_MACHINE.Name']} | Account: {row['SUBSCRIPTION.Name']} | Current Comment: {row['comment']}")
        else:
            print("No matching Windows servers found in these accounts.")

if __name__ == "__main__":
    find_unmanaged_windows()
