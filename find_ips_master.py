import pandas as pd

def find_ips_in_master():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_29th Apr..xlsx'
    search_ips = [
        '10.196.252.199', '10.196.252.105', '10.196.252.121', 
        '10.196.252.220', '10.196.72.102', '10.196.72.122'
    ]
    
    df = pd.read_excel(path, sheet_name='Non-ASG Data')
    print("| Matching IP | Hostname | OS | Account |")
    print("| :--- | :--- | :--- | :--- |")
    
    found = False
    for _, row in df.iterrows():
        ip_str = str(row.get('NETWORK_ADDRESS.Name', ''))
        for sip in search_ips:
            if sip in ip_str:
                print(f"| {sip} | {row['VIRTUAL_MACHINE.Name']} | {row['VIRTUAL_MACHINE.operatingSystem']} | {row['SUBSCRIPTION.Name']} |")
                found = True
                
    if not found:
        print("| No matches found in Master file | - | - | - |")

if __name__ == "__main__":
    find_ips_in_master()
