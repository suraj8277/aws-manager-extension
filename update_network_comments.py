import pandas as pd
import os

def update_specific_network_comments():
    may_path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    target_comment = "acess has been sorted we will raise change in upcoming week"
    
    # Hostnames identified from the IP matching
    target_hostnames = [
        'osttra-network-prod-zabbix-server-eu-west-1a', 
        'osttra-network-prod-ntp-eu-west-1a', 
        'osttra-network-prod-ntp-eu-west-1b', 
        'osttra-network-prod-zabbix-server-eu-west-1b', 
        'osttra-network-prod-ntp-us-east-1a', 
        'osttra-network-prod-ntp-us-east-1b'
    ]
    
    print("Reading May file...")
    all_sheets = pd.read_excel(may_path, sheet_name=None)
    
    updated_any = False
    for sheet_name in ['Tanium(NonASG)', 'Cortex(NonASG)']:
        if sheet_name in all_sheets:
            df = all_sheets[sheet_name]
            print(f"Processing sheet: {sheet_name}")
            
            # Match by Hostname
            mask = df['VIRTUAL_MACHINE.Name'].isin(target_hostnames)
            
            if mask.any():
                df.loc[mask, 'comment'] = target_comment
                all_sheets[sheet_name] = df
                updated_any = True
                print(f"Updated {mask.sum()} matching instances in {sheet_name}.")

    if updated_any:
        print("Saving updated May file...")
        with pd.ExcelWriter(may_path, engine='openpyxl') as writer:
            for name, sheet_df in all_sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
        print("Success! Network instance comments updated.")
    else:
        print("No matching hostnames found in the sheets.")

if __name__ == "__main__":
    update_specific_network_comments()
