import openpyxl
import sys

def read_ips_from_excel(input_filename: str) -> None:
    """
    Reads an existing EC2 inventory Excel file and prints all IPs
    from the 'Private IPv4' column.
    """
    try:
        # Load the source workbook
        print(f"Opening report '{input_filename}'...")
        workbook = openpyxl.load_workbook(input_filename)
        sheet = workbook.active
    except FileNotFoundError:
        print(f"Error: The file '{input_filename}' was not found.")
        print("Please make sure the file is in the same directory as this script.")
        return
    except Exception as e:
        print(f"An error occurred while opening the file: {e}")
        return

    # Find the column index for 'Private IPv4'
    header_row = sheet[1]
    ip_column_index = -1
    
    # Enumerate from 1 for Excel columns
    for idx, cell in enumerate(header_row, 1): 
        if cell.value == 'Private IPv4':
            ip_column_index = idx
            break
            
    if ip_column_index == -1:
        print("Error: Could not find the 'Private IPv4' column in the report.")
        print("Please ensure the header is correct.")
        return

    print("Found 'Private IPv4' column. Reading all IPs...\n")
    
    ip_list = []
    # Iterate through the data rows (starting from row 2)
    for row in sheet.iter_rows(min_row=2, values_only=True):
        # Get the IP address from the correct column (using 0-based index)
        ip_address = row[ip_column_index - 1] 
        
        if ip_address and isinstance(ip_address, str) and ip_address != 'N/A':
            ip_list.append(ip_address)

    if not ip_list:
        print("No IP addresses found in the file (excluding 'N/A').")
    else:
        print(f"--- Successfully read {len(ip_list)} IP addresses ---")
        for ip in ip_list:
            print(ip)

def main():
    # You can change this filename directly in the script
    # or pass it as an argument when you run it.
    
    if len(sys.argv) > 1:
        filename_to_read = sys.argv[1]
    else:
        # ---!!!---
        # IMPORTANT: Change this to your exact filename
        # ---!!!---
        filename_to_read = "aws_ec2_inventory_linux_20251112_121747.xlsx"
        print(f"No filename given, defaulting to '{filename_to_read}'")

    read_ips_from_excel(filename_to_read)

if __name__ == '__main__':
    main()