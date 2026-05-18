import subprocess
import csv
import sys
import os

# Configuration: Priority order for inventory files
INVENTORY_FILES = [
    'gcp_servers.csv',  # Your provided data
    r'Inventory_0411\without_ASG-cloud.csv',
    r'Inventory_0411\with_ASG_Cloud.csv'
]

def find_server_details(server_name):
    """
    Searches through CSV inventory files to find project and zone for a server.
    """
    for file_path in INVENTORY_FILES:
        if not os.path.exists(file_path):
            continue
            
        with open(file_path, mode='r', encoding='utf-8') as f:
            # Determine format based on filename
            if 'gcp_servers.csv' in file_path:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Name') == server_name:
                        zone = row.get('Zone')
                        project = row.get('Project ID')
                        if zone and zone != 'N/A':
                            return project, zone
            else:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('VIRTUAL_MACHINE.Name') == server_name:
                        region_info = row.get('REGION.Name', '')
                        if '(' in region_info and ')' in region_info:
                            region = region_info.split('(')[0].strip()
                            project = region_info.split('(')[1].replace(')', '').strip()
                            # Default to -a zone if only region is known
                            zone = f"{region}-a" 
                            return project, zone
    return None, None

def main():
    if len(sys.argv) < 2:
        server_name = input("Enter server name: ")
    else:
        server_name = sys.argv[1]

    print(f"Searching for details of server: {server_name}...")
    project, zone = find_server_details(server_name)

    if not project or not zone:
        print(f"Error: Could not find valid SSH details for '{server_name}'.")
        sys.exit(1)

    print(f"Found: Project={project}, Zone={zone}")
    print(f"Connecting to {server_name} via internal IP...")

    # Modified to use --internal-ip as requested
    gcloud_exec = "gcloud.cmd" if os.name == 'nt' else "gcloud"
    cmd = [
        gcloud_exec, "compute", "ssh",
        "--zone", zone,
        server_name,
        "--internal-ip",
        "--project", project
    ]

    try:
        # Run the command and let it take over the terminal
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\nSSH connection closed or failed: {e}")
    except FileNotFoundError:
        print("Error: 'gcloud' command not found. Please ensure Google Cloud SDK is installed.")

if __name__ == "__main__":
    main()
