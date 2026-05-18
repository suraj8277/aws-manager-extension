import boto3
from botocore.exceptions import ClientError, ProfileNotFound
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional

# --- Configuration ---
OUTPUT_FILENAME_BASE = 'aws_ec2_inventory_linux'

def get_ssm_status_map(session: boto3.Session, region: str) -> Dict[str, str]:
    """
    Fetches the SSM status for instances in a specific region.
    Returns a dictionary: { 'i-xyz': 'Online', 'i-abc': 'ConnectionLost' }
    """
    ssm_map = {}
    try:
        ssm_client = session.client('ssm', region_name=region)
        paginator = ssm_client.get_paginator('describe_instance_information')
        
        # We handle pagination to get all managed instances
        for page in paginator.paginate():
            for item in page['InstanceInformationList']:
                instance_id = item['InstanceId']
                # PingStatus is usually 'Online' or 'ConnectionLost'
                ssm_map[instance_id] = item['PingStatus']
                
    except ClientError as e:
        # If the user doesn't have ssm:DescribeInstanceInformation permission, 
        # we treat it as unknown/empty rather than crashing the whole script.
        print(f"Warning: Could not fetch SSM info for {region}: {e}")
    except Exception as e:
        print(f"Unexpected error fetching SSM info in {region}: {e}")
        
    return ssm_map

def get_all_ec2_instances(profile_name: str, region_input: str) -> Optional[List[Dict[str, Any]]]:
    """
    Connects to AWS using a specific profile and fetches details of all EC2 instances
    and their SSM status.
    """
    print(f"Attempting to connect to AWS with profile: '{profile_name}'...")
    try:
        session = boto3.Session(profile_name=profile_name)
    except ProfileNotFound:
        print(f"Error: The AWS profile '{profile_name}' was not found.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during session creation: {e}")
        return None

    all_instances = []
    regions_to_scan = []

    if region_input.lower() == 'all':
        print("Finding all available EC2 regions...")
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
        
        # 1. Fetch SSM Statuses for this region first
        ssm_status_map = get_ssm_status_map(session, region)

        try:
            ec2_client = session.client('ec2', region_name=region)
            paginator = ec2_client.get_paginator('describe_instances')
            
            page_iterator = paginator.paginate(
                Filters=[{'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}]
            )
            
            regional_instances_found = 0
            for page in page_iterator:
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        instance['Region'] = region
                        
                        # 2. Check if this specific instance ID exists in our SSM map
                        i_id = instance.get('InstanceId')
                        # If found in map, use the status (e.g., 'Online'). If not, assume 'Not Managed'.
                        instance['SSMStatus'] = ssm_status_map.get(i_id, 'Not Managed')
                        
                        all_instances.append(instance)
                        regional_instances_found += 1
            
            if regional_instances_found > 0:
                print(f"Found {regional_instances_found} instances in {region}.")

        except ClientError as e:
            if e.response['Error']['Code'] in ['AuthFailure', 'UnauthorizedOperation']:
                print(f"Could not access region '{region}'. Skipping.")
            else:
                print(f"An unexpected error occurred in region {region}: {e}")
            continue 

    print(f"\nTotal instances found across all scanned regions: {len(all_instances)}.")
    return all_instances

def write_instances_to_csv(instances: List[Dict[str, Any]], filename: str) -> None:
    """
    Writes the collected instance data to a CSV file.
    """
    if not instances:
        print("No instance data to write. Exiting.")
        return

    # Updated Headers to include SSM Status
    headers = [
        'Instance Name', 'Instance ID', 'Private IPv4', 'Instance State', 
        'SSM Status', 'Instance Type', 'Region', 'Availability Zone', 
        'Subnet ID', 'VPC ID', 'Platform'
    ]

    print(f"\nFiltering for Linux instances and writing data to '{filename}'...")
    
    try:
        with open(filename, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(headers)

            linux_instances_written = 0
            for instance in instances:
                platform_details = instance.get('PlatformDetails', 'Linux/UNIX')
                if 'Windows' in platform_details:
                    continue 

                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                
                # Assemble the row data with the new SSM field
                row = [
                    tags.get('Name', 'N/A'),
                    instance.get('InstanceId', 'N/A'),
                    instance.get('PrivateIpAddress', 'N/A'),
                    instance.get('State', {}).get('Name', 'N/A'),
                    instance.get('SSMStatus', 'N/A'),  # New Column Data
                    instance.get('InstanceType', 'N/A'),
                    instance.get('Region', 'N/A'),
                    instance.get('Placement', {}).get('AvailabilityZone', 'N/A'),
                    instance.get('SubnetId', 'N/A'),
                    instance.get('VpcId', 'N/A'),
                    platform_details
                ]
                
                writer.writerow(row)
                linux_instances_written += 1
            
            print(f"Wrote {linux_instances_written} Linux instances to the report.")
            print(f"\nSuccess! CSV report saved as '{filename}'")

    except IOError as e:
        print(f"Error saving the CSV file: {e}")

def main() -> None:
    profile_name = input("Please enter the AWS profile name to use [default]: ") or 'default'
    region_name = input("Enter an AWS region (e.g., us-west-2) or 'all' to scan all regions: ")

    if not region_name:
        print("Region cannot be empty.")
        return

    instances = get_all_ec2_instances(profile_name, region_name)
    
    if instances is not None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{OUTPUT_FILENAME_BASE}_{timestamp}.csv"
        write_instances_to_csv(instances, output_file)

if __name__ == '__main__':
    main()