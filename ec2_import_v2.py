import boto3
from botocore.exceptions import ClientError, ProfileNotFound
import csv
from datetime import datetime
from typing import List, Dict, Any, Optional
import os
import glob
import json
import re

# --- Configuration ---
# The base name for the output file. A timestamp will be added to it.
OUTPUT_FILENAME_BASE = 'aws_ec2_inventory_linux'
SSO_REGION = 'us-east-1' # Change to your AWS SSO region if different

def get_aws_session(target: str) -> Optional[boto3.Session]:
    """
    Creates a boto3 Session. If a 12-digit Account ID is provided, it uses 
    the active AWS SSO cached token to assume a role in that account.
    Otherwise, it treats the input as a standard AWS profile name.
    """
    target = target.strip()
    
    # Check if input is a 12-digit AWS Account ID
    if re.match(r'^\d{12}$', target):
        print(f"Detected 12-digit Account ID. Attempting to connect via AWS SSO...")
        sso_cache_dir = os.path.expanduser('~/.aws/sso/cache')
        access_token = None
        
        # Find the active access token in the local AWS SSO cache
        for filename in glob.glob(os.path.join(sso_cache_dir, '*.json')):
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)
                    if 'accessToken' in data:
                        # Check if the token has expired
                        if 'expiresAt' in data:
                            expires_at_str = data['expiresAt']
                            # Strip milliseconds and 'Z' for safe parsing
                            expires_at_str = expires_at_str.split('.')[0].replace('Z', '')
                            try:
                                expires_time = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M:%S')
                                if expires_time < datetime.utcnow():
                                    continue  # Token is expired, check next file
                            except ValueError:
                                pass
                        access_token = data['accessToken']
                        break
            except Exception:
                continue
                
        if not access_token:
            print("Error: No active AWS SSO token found. Please run 'aws sso login' first.")
            return None
            
        try:
            sso_client = boto3.client('sso', region_name=SSO_REGION)
            roles_resp = sso_client.list_account_roles(accessToken=access_token, accountId=target)
            roles = roles_resp.get('roleList', [])
            
            if not roles:
                print(f"Error: No assigned roles found for account {target}.")
                return None
                
            # Pick the first available role assigned to you for this account
            role_name = roles[0]['roleName']
            print(f"Assuming role '{role_name}' in account {target}...")
            
            creds_resp = sso_client.get_role_credentials(
                roleName=role_name, accountId=target, accessToken=access_token
            )
            creds = creds_resp['roleCredentials']
            
            return boto3.Session(
                aws_access_key_id=creds['accessKeyId'],
                aws_secret_access_key=creds['secretAccessKey'],
                aws_session_token=creds['sessionToken']
            )
        except Exception as e:
            print(f"Failed to create SSO session: {e}")
            return None
    else:
        # Treat as standard profile name
        print(f"Attempting to connect to AWS with profile: '{target}'...")
        try:
            return boto3.Session(profile_name=target)
        except ProfileNotFound:
            print(f"Error: The AWS profile '{target}' was not found.")
            return None

def get_all_ec2_instances(account_or_profile: str, region_input: str) -> Optional[List[Dict[str, Any]]]:
    """
    Connects to AWS using an account ID or profile and fetches details of all EC2 instances
    from either a single specified region or all available regions.
    """
    session = get_aws_session(account_or_profile)
    if not session:
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

def write_instances_to_csv(instances: List[Dict[str, Any]], filename: str) -> None:
    """
    Writes the collected instance data to a CSV file, filtering for Linux/UNIX only.
    """
    if not instances:
        print("No instance data to write. Exiting.")
        return

    # Define headers
    headers = [
        'Instance Name', 'Instance ID', 'Private IPv4', 'Instance State', 'Instance Type',
        'Region', 'Availability Zone', 'Subnet ID', 'VPC ID', 'Platform'
    ]

    print(f"\nFiltering for Linux instances and writing data to '{filename}'...")
    
    try:
        # Open file in write mode with newline='' to prevent blank lines between rows on Windows
        with open(filename, mode='w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            
            # Write the header row
            writer.writerow(headers)

            linux_instances_written = 0
            for instance in instances:
                # Get platform details. Defaults to 'Linux/UNIX' if not present
                platform_details = instance.get('PlatformDetails', 'Linux/UNIX')

                # If the platform details contain 'Windows', skip this instance.
                if 'Windows' in platform_details:
                    continue 

                # Create a dictionary of tags for easier lookup
                tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                
                # Assemble the row data
                row = [
                    tags.get('Name', 'N/A'),
                    instance.get('InstanceId', 'N/A'),
                    instance.get('PrivateIpAddress', 'N/A'),
                    instance.get('State', {}).get('Name', 'N/A'),
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
    """
    Main function to orchestrate fetching data and writing the report.
    """
    target_input = input("Enter AWS Account ID (12 digits) OR Profile Name [default]: ") or 'default'
    region_name = input("Enter an AWS region (e.g., us-west-2) or 'all' to scan all regions [all]: ") or 'all'

    instances = get_all_ec2_instances(target_input, region_name)
    
    if instances is not None:
        # Generate a unique filename with a timestamp and .csv extension
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{OUTPUT_FILENAME_BASE}_{timestamp}.csv"
        write_instances_to_csv(instances, output_file)

if __name__ == '__main__':
    main()