import pandas as pd

def search_ips():
    path = r'C:\Users\SurajKumar\Documents\python\Tanium_Cortex_Pending_13th May.xlsx'
    search_ips = [
        '10.196.252.199', '10.196.252.105', '10.196.252.121', 
        '10.196.252.220', '10.196.72.102', '10.196.72.122'
    ]
    
    xl = pd.ExcelFile(path)
    found_any = False
    
    print("| Sheet | Matching IP | Hostname | OS | Status |")
    print("| :--- | :--- | :--- | :--- | :--- |")
    
    for sheet_name in xl.sheet_names:
        df = pd.read_excel(xl, sheet_name=sheet_name)
        
        # We check common IP columns: 'NETWORK_ADDRESS.Name' or 'Private IPv4'
        ip_col = None
        for col in ['NETWORK_ADDRESS.Name', 'Private IPv4', 'IP Address']:
            if col in df.columns:
                ip_col = col
                break
        
        if ip_col:
            # Filter rows where IP is in our search list
            matches = df[df[ip_col].astype(str).isin(search_ips)]
            for _, row in matches.iterrows():
                name = row.get('VIRTUAL_MACHINE.Name', row.get('Instance Name', 'N/A'))
                os_val = row.get('VIRTUAL_MACHINE.operatingSystem', row.get('Platform', 'N/A'))
                status = row.get('VIRTUAL_MACHINE.status', row.get('Instance State', 'N/A'))
                ip_val = row[ip_col]
                
                print(f"| {sheet_name} | {ip_val} | {name} | {os_val} | {status} |")
                found_any = True
                
    if not found_any:
        print("| N/A | No matches found | - | - | - |")

if __name__ == "__main__":
    search_ips()
