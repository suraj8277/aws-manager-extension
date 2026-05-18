import boto3
from botocore.exceptions import ClientError, ProfileNotFound
import openpyxl
from openpyxl.styles import Font
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration ---
# The base name for the output file. A timestamp will be added to it.
OUTPUT_FILENAME_BASE = 'aws_ec2_inventory_linux'

def get_all_ec2_instances(profile_name: str, region_input: str) -> Optional[List[Dict[str, Any]]]:
    """
    Connects to AWS using a specific profile and fetches details of all EC2 instances
    from either a single specified region or all available regions.
    """
    print(f"Attempting to connect to AWS with profile: '{profile_name}'...")
    try:
        session = boto3.Session(profile_name=profile_name)
    except ProfileNotFound:
        print(f"Error: The AWS profile '{profile_name}' was not found.")
        print("Please ensure it is configured in your ~/.aws/credentials file.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during session creation: {e}")
        return None

    all_instances = []
    regions_to_scan = []

    if region_input.lower() == 'all':
        print("Finding all available EC2 regions...")
        # A base client is needed to find all other regions
        base_ec2_client = session.client('ec2', region_name='us-east-1')
        try:
            response = base_ec2_client.describe_regions()
            regions_to_scan = [region['RegionName'] for region in response['Regions']]
            print(f"Found {len(regions_to_scan)} regions to scan.")
        except ClientError as e:
            print(f"Error fetching AWS regions: {e}")
            return None
    else:
        regions_to_scan.append(region_input)

    for region in regions_to_scan:
        print(f"\n--- Scanning Region: {region} ---")
        try:
            ec2_client = session.client('ec2', region_name=region)
            paginator = ec2_client.get_paginator('describe_instances')
            # Filter for instances that are not terminated
            page_iterator = paginator.paginate(
                Filters=[{'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}]
            )
            
            regional_instances_found = 0
            for page in page_iterator:
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        # Add the region info directly to the instance data
                        instance['Region'] = region
                        all_instances.append(instance)
                        regional_instances_found += 1
            
            if regional_instances_found > 0:
                print(f"Found {regional_instances_found} instances in {region}.")

        except ClientError as e:
            # This often happens for regions that are not enabled for the account
            if e.response['Error']['Code'] in ['AuthFailure', 'UnauthorizedOperation']:
                print(f"Could not access region '{region}'. It might not be enabled for your account. Skipping.")
            else:
                print(f"An unexpected error occurred in region {region}: {e}")
            continue  # Move to the next region

    print(f"\nTotal instances found across all scanned regions: {len(all_instances)}.")
    return all_instances

def write_instances_to_excel(instances: List[Dict[str, Any]], filename: str) -> None:
    """
    Writes the collected instance data to an Excel file, filtering for Linux/UNIX only.
    """
    if not instances:
        print("No instance data to write. Exiting.")
        return

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'EC2 Inventory (Linux Only)'

    # Define and write the header row in the requested sequence
    headers = [
        'Instance Name', 'Instance ID', 'Private IPv4', 'Instance State', 'Instance Type',
        'Region', 'Availability Zone', 'Platform'
    ]
    sheet.append(headers)

    # Make the header row bold
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    print(f"\nFiltering for Linux instances and writing data to '{filename}'...")
    linux_instances_written = 0
    for instance in instances:
        # Get platform details. Defaults to 'Linux/UNIX' if not present, which is
        # the common case for Amazon Linux, Ubuntu, etc.
        platform_details = instance.get('PlatformDetails', 'Linux/UNIX')

        # --- CONDITION ADDED HERE ---
        # If the platform details contain 'Windows', skip this instance.
        if 'Windows' in platform_details:
            continue  # Skip to the next instance

        # Create a dictionary of tags for easier lookup
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        
        # Assemble the row data in the new sequence
        row = [
            tags.get('Name', 'N/A'),
            instance.get('InstanceId', 'N/A'),
            instance.get('PrivateIpAddress', 'N/A'),
            instance.get('State', {}).get('Name', 'N/A'),
            instance.get('InstanceType', 'N/A'),
            instance.get('Region', 'N/A'),
            instance.get('Placement', {}).get('AvailabilityZone', 'N/A'),
            platform_details
        ]
        sheet.append(row)
        linux_instances_written += 1
    
    print(f"Wrote {linux_instances_written} Linux instances to the report.")

    try:
        workbook.save(filename)
        print(f"\nSuccess! Excel report saved as '{filename}'")
    except Exception as e:
        print(f"Error saving the Excel file: {e}")

def main() -> None:
    """
    Main function to orchestrate fetching data and writing the report.
    """
    profile_name = input("Please enter the AWS profile name to use [default]: ") or 'default'
    region_name = input("Enter an AWS region (e.g., us-west-2) or 'all' to scan all regions: ")

    if not region_name:
        print("Region cannot be empty. Please run the script again.")
        return

    instances = get_all_ec2_instances(profile_name, region_name)
    
    if instances is not None:
        # Generate a unique filename with a timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{OUTPUT_FILENAME_BASE}_{timestamp}.xlsx"
        write_instances_to_excel(instances, output_file)

if __name__ == '__main__':
    main()
