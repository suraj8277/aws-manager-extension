import pandas as pd

def cross_check():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    names = [
        'osttra-network-prod-zabbix-server-eu-west-1a', 
        'osttra-network-prod-ntp-eu-west-1a', 
        'osttra-network-prod-ntp-eu-west-1b', 
        'osttra-network-prod-zabbix-server-eu-west-1b', 
        'osttra-network-prod-ntp-us-east-1a', 
        'osttra-network-prod-ntp-us-east-1b'
    ]
    
    xl = pd.ExcelFile(path)
    print("--- Searching for Hostnames in May Pending File ---")
    found = False
    
    for sn in xl.sheet_names:
        if 'Pivot' in sn: continue
        df = pd.read_excel(xl, sheet_name=sn)
        matches = df[df['VIRTUAL_MACHINE.Name'].isin(names)]
        for _, row in matches.iterrows():
            print(f"Match Found in sheet '{sn}': {row['VIRTUAL_MACHINE.Name']} (ID: {row['VIRTUAL_MACHINE.externalId']})")
            found = True
            
    if not found:
        print("No matching hostnames found in the May file.")

if __name__ == "__main__":
    cross_check()
