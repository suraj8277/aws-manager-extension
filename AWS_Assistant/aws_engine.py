import boto3
import json
import os
import subprocess
import configparser
import argparse
import csv
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
AWS_CONFIG_PATH = os.path.expanduser('~/.aws/config')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, 'aws_inventory_memory.json')

class AWSUniversalEngine:
    def __init__(self):
        self.config = configparser.ConfigParser()
        if os.path.exists(AWS_CONFIG_PATH):
            self.config.read(AWS_CONFIG_PATH)

    def list_local_profiles(self):
        """Lists profiles already configured in ~/.aws/config."""
        profiles = []
        for section in self.config.sections():
            if section.startswith('profile '):
                profiles.append(section.replace('profile ', '').strip())
            elif section == 'default':
                profiles.append('default')
        return profiles

    def get_sso_session_details(self):
        """Finds the first available sso-session and its details."""
        for section in self.config.sections():
            if section.startswith('sso-session '):
                return {
                    "name": section.replace('sso-session ', '').strip(),
                    "url": self.config.get(section, 'sso_start_url'),
                    "region": self.config.get(section, 'sso_region')
                }
        return None

    # --- SSO Account Discovery (Dynamic) ---
    def discover_sso_accounts(self, profile=None):
        """Lists all accounts accessible via the given SSO profile or session."""
        try:
            # If no profile is provided, try to find one that uses an sso-session
            if not profile:
                for section in self.config.sections():
                    if section.startswith('profile ') and self.config.has_option(section, 'sso_session'):
                        profile = section.replace('profile ', '').strip()
                        break
            
            if not profile:
                return {"error": "No SSO profile found in config."}

            cmd = ["aws", "sso", "list-accounts", "--profile", profile, "--output", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout).get('accountList', [])
        except Exception as e:
            return {"error": str(e)}

    def discover_sso_roles(self, profile, account_id):
        """Lists roles accessible for a specific account."""
        try:
            cmd = ["aws", "sso", "list-account-roles", "--profile", profile, "--account-id", account_id, "--output", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout).get('roleList', [])
        except Exception as e:
            return {"error": str(e)}

    # --- Profile Management (Static Code) ---
    def add_profile(self, name, start_url, sso_region, account_id, role_name, region):
        """Adds/Updates a profile using the modern sso-session format."""
        session_name = f"session-{sso_region}"
        sso_section = f'sso-session {session_name}'
        profile_section = f'profile {name}'
        
        if sso_section not in self.config.sections():
            self.config.add_section(sso_section)
            self.config.set(sso_section, 'sso_start_url', start_url)
            self.config.set(sso_section, 'sso_region', sso_region)
            self.config.set(sso_section, 'sso_registration_scopes', 'sso:account:access')

        if profile_section not in self.config.sections():
            self.config.add_section(profile_section)
        
        self.config.set(profile_section, 'sso_session', session_name)
        self.config.set(profile_section, 'sso_account_id', account_id)
        self.config.set(profile_section, 'sso_role_name', role_name)
        self.config.set(profile_section, 'region', region)
        self.config.set(profile_section, 'output', 'json')
        
        with open(AWS_CONFIG_PATH, 'w') as f:
            self.config.write(f)
        return f"Success: Profile '{name}' configured."

    def delete_profile(self, name):
        """Safely removes a profile from ~/.aws/config."""
        section = f'profile {name}' if name != 'default' else 'default'
        if self.config.has_section(section):
            self.config.remove_section(section)
            with open(AWS_CONFIG_PATH, 'w') as f:
                self.config.write(f)
            return f"Success: Profile '{name}' removed."
        return f"Error: Profile '{name}' not found."

    # --- Strictly Read-Only Inventory Scan ---
    def _get_ssm_statuses(self, session, region, instance_ids):
        """Helper to fetch SSM Ping Status in chunks."""
        if not instance_ids:
            return {}
        ssm_status_map = {}
        try:
            ssm_client = session.client('ssm', region_name=region)
            for i in range(0, len(instance_ids), 50):
                chunk = instance_ids[i:i + 50]
                paginator = ssm_client.get_paginator('describe_instance_information') # READ-ONLY
                for page in paginator.paginate(Filters=[{'Key': 'InstanceIds', 'Values': chunk}]):
                    for info in page.get('InstanceInformationList', []):
                        ssm_status_map[info['InstanceId']] = info.get('PingStatus', 'Unknown')
        except Exception:
            pass
        return ssm_status_map

    def scan_region(self, profile, region):
        """UNIVERSAL SCAN: Fetches the FULL raw metadata for every instance, including SSM status."""
        try:
            session = boto3.Session(profile_name=profile, region_name=region)
            ec2 = session.client('ec2')
            regional_instances = []
            paginator = ec2.get_paginator('describe_instances') # READ-ONLY
            for page in paginator.paginate():
                for res in page['Reservations']:
                    for inst in res['Instances']:
                        regional_instances.append(inst)
            
            if not regional_instances:
                return []
                
            instance_ids = [inst['InstanceId'] for inst in regional_instances]
            ssm_statuses = self._get_ssm_statuses(session, region, instance_ids)
            
            instances = []
            for inst in regional_instances:
                inst['__Assistant_SSM_PingStatus'] = ssm_statuses.get(inst['InstanceId'], 'Not Managed')
                inst['__Assistant_Profile'] = profile
                inst['__Assistant_Region'] = region
                instances.append(inst)
                
            return instances
        except Exception:
            return []

    def export_csv(self, profile, category, output_path):
        """Exports specific categories of data for a profile to a CSV file."""
        if not os.path.exists(CACHE_FILE):
            return "Error: Local memory not found. Please run 'refresh' first."

        with open(CACHE_FILE, 'r') as f:
            memory = json.load(f)

        instances = [i for i in memory.get('raw_data', []) if i.get('__Assistant_Profile') == profile]
        if not instances:
            return f"No instances found in memory for profile '{profile}'."

        rows = []
        for inst in instances:
            tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
            name = tags.get('Name', 'N/A')
            
            if category == 'overview':
                rows.append({
                    "Name": name,
                    "InstanceId": inst.get('InstanceId'),
                    "State": inst.get('State', {}).get('Name'),
                    "PrivateIP": inst.get('PrivateIpAddress'),
                    "InstanceType": inst.get('InstanceType'),
                    "SSMStatus": inst.get('__Assistant_SSM_PingStatus')
                })
            elif category == 'network':
                sgs = ", ".join([sg.get('GroupName') for sg in inst.get('SecurityGroups', [])])
                rows.append({
                    "Name": name,
                    "InstanceId": inst.get('InstanceId'),
                    "VpcId": inst.get('VpcId'),
                    "SubnetId": inst.get('SubnetId'),
                    "SecurityGroups": sgs
                })
            elif category == 'security':
                iam = inst.get('IamInstanceProfile', {}).get('Arn', 'N/A')
                rows.append({
                    "Name": name,
                    "InstanceId": inst.get('InstanceId'),
                    "IAMRole": iam,
                    "KeyPair": inst.get('KeyName'),
                    "Platform": inst.get('PlatformDetails')
                })
            elif category == 'tags':
                row = {"Name": name, "InstanceId": inst.get('InstanceId')}
                for k, v in tags.items():
                    if k != 'Name': row[f"Tag:{k}"] = v
                rows.append(row)

        if not rows:
            return f"No data to export for category '{category}'."

        # Get all unique keys for headers
        keys = set()
        for r in rows: keys.update(r.keys())
        headers = sorted(list(keys))

        try:
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                writer.writerows(rows)
            return f"Success: Exported {len(rows)} instances to {output_path}."
        except Exception as e:
            return f"Error writing CSV: {e}"

    def refresh_inventory(self, profiles=None):
        """Refreshes the local JSON memory with full metadata snapshots, merging with existing data."""
        target_profiles = profiles if profiles else self.list_local_profiles()
        
        # Load existing data to merge
        existing_data = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    old_memory = json.load(f)
                    # Keep data for profiles we are NOT currently scanning
                    existing_data = [i for i in old_memory.get('raw_data', []) if i.get('__Assistant_Profile') not in target_profiles]
            except Exception:
                existing_data = []

        new_inventory = []
        for p in target_profiles:
            # Check Auth
            try:
                session = boto3.Session(profile_name=p)
                sts = session.client('sts')
                sts.get_caller_identity() # READ-ONLY
            except Exception:
                # MANDATORY CHANGE: Do not trigger login automatically
                print(f"AUTH_REQUIRED: Profile '{p}' needs SSO login.")
                continue

            print(f"Scanning profile: {p}...")
            # Discover regions
            try:
                ec2_client = boto3.Session(profile_name=p).client('ec2', region_name='us-east-1')
                regions = [r['RegionName'] for r in ec2_client.describe_regions()['Regions']]
            except:
                continue

            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(self.scan_region, p, reg) for reg in regions]
                for f in as_completed(futures):
                    new_inventory.extend(f.result())
        
        # Merge: New data + preserved existing data
        merged_inventory = existing_data + new_inventory
        
        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_instances": len(merged_inventory),
            "raw_data": merged_inventory # This is the "Universal Memory"
        }
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=4, default=str) # str handles datetime objects in JSON
        
        return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["refresh", "list-profiles", "discover-accounts", "discover-roles", "add-profile", "delete-profile", "export-csv"])
    parser.add_argument("--profile", help="AWS Profile name")
    parser.add_argument("--account-id", help="AWS Account ID for role discovery")
    parser.add_argument("--category", choices=["overview", "network", "security", "tags"], help="Category for CSV export")
    parser.add_argument("--output", help="Output path for CSV file")
    # Args for add-profile
    parser.add_argument("--name")
    parser.add_argument("--url")
    parser.add_argument("--sso-region")
    parser.add_argument("--role")
    parser.add_argument("--region")

    args = parser.parse_args()
    engine = AWSUniversalEngine()

    if args.command == "refresh":
        res = engine.refresh_inventory([args.profile] if args.profile else None)
        print(f"Success: Found {res['total_instances']} instances.")
    elif args.command == "list-profiles":
        print(json.dumps(engine.list_local_profiles(), indent=2))
    elif args.command == "discover-accounts":
        print(json.dumps(engine.discover_sso_accounts(args.profile), indent=2))
    elif args.command == "discover-roles":
        print(json.dumps(engine.discover_sso_roles(args.profile, args.account_id), indent=2))
    elif args.command == "add-profile":
        print(engine.add_profile(args.name, args.url, args.sso_region, args.account_id, args.role, args.region))
    elif args.command == "delete-profile":
        print(engine.delete_profile(args.name))
    elif args.command == "export-csv":
        print(engine.export_csv(args.profile, args.category, args.output))
