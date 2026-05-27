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
    def _get_active_sso_token(self):
        """Attempts to find a valid SSO access token in the local cache."""
        cache_dir = os.path.expanduser('~/.aws/sso/cache')
        if not os.path.exists(cache_dir):
            return None
        
        for filename in os.listdir(cache_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(cache_dir, filename), 'r') as f:
                        data = json.load(f)
                        # Check if it has an access token and hasn't expired
                        if 'accessToken' in data and 'expiresAt' in data:
                            expires_at = datetime.strptime(data['expiresAt'].replace('Z', ''), "%Y-%m-%dT%H:%M:%S")
                            if expires_at > datetime.utcnow():
                                return data['accessToken']
                except Exception:
                    continue
        return None

    def discover_sso_accounts(self, profile=None):
        """Lists all accounts accessible via the given SSO profile or session."""
        try:
            token = self._get_active_sso_token()
            if token:
                # Use raw token if available
                cmd = ["aws", "sso", "list-accounts", "--access-token", token, "--region", "eu-west-2", "--output", "json"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return json.loads(result.stdout).get('accountList', [])

            # Fallback to profile-based
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
            token = self._get_active_sso_token()
            if token:
                cmd = ["aws", "sso", "list-account-roles", "--access-token", token, "--account-id", account_id, "--region", "eu-west-2", "--output", "json"]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return json.loads(result.stdout).get('roleList', [])

            cmd = ["aws", "sso", "list-account-roles", "--profile", profile, "--account-id", account_id, "--output", "json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return json.loads(result.stdout).get('roleList', [])
        except Exception as e:
            return {"error": str(e)}

    def discover_all_sso_mappings(self, profile=None):
        """Discovers all Account+Role combinations accessible in the current SSO session."""
        accounts = self.discover_sso_accounts(profile)
        if isinstance(accounts, dict) and "error" in accounts:
            return accounts

        mappings = []
        
        # Use threading to fetch roles for all accounts in parallel
        def fetch_roles(account):
            roles = self.discover_sso_roles(profile, account['accountId'])
            if isinstance(roles, list):
                return [{
                    "account_id": account['accountId'],
                    "account_name": account['accountName'],
                    "role_name": role['roleName']
                } for role in roles]
            return []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(fetch_roles, acc) for acc in accounts]
            for f in as_completed(futures):
                mappings.extend(f.result())
        
        return mappings

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

    def bulk_add_profiles(self, mappings_input, start_url, sso_region, region):
        """Adds multiple profiles at once from a JSON list of mappings or a file path starting with '@'."""
        if mappings_input.startswith('@'):
            file_path = mappings_input[1:]
            with open(file_path, 'r') as f:
                mappings = json.load(f)
        else:
            mappings = json.loads(mappings_input)
            
        results = []
        for m in mappings:
            # Generate a clean name: account-name-role-name (lowercase, no spaces)
            safe_acc = m['account_name'].lower().replace(' ', '-')
            safe_role = m['role_name'].lower().replace(' ', '-')
            profile_name = f"{safe_acc}-{safe_role}"
            
            res = self.add_profile(profile_name, start_url, sso_region, m['account_id'], m['role_name'], region)
            results.append(res)
        
        return f"Bulk Add Complete: {len(results)} profiles processed."

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

    def _print_box_table(self, rows, title=None):
        """Prints a list of dictionaries as a Unicode box-drawing table."""
        if not rows: return
        
        headers = list(rows[0].keys())
        # Calculate max width for each column
        widths = {h: len(h) for h in headers}
        for r in rows:
            for h in headers:
                val = str(r.get(h, ''))
                widths[h] = max(widths[h], len(val))

        # Helper to draw a line
        def draw_line(left, middle, right, cross):
            line = left
            for i, h in enumerate(headers):
                line += middle * (widths[h] + 2)
                if i < len(headers) - 1: line += cross
            line += right
            print(line)

        if title:
            print(f"\n--- {title} ---")

        # Top border
        draw_line('┌', '─', '┐', '┬')
        
        # Headers
        header_row = "│"
        for h in headers:
            header_row += f" {h:<{widths[h]}} │"
        print(header_row)
        
        # Header separator
        draw_line('├', '─', '┤', '┼')
        
        # Data rows
        for r in rows:
            row_str = "│"
            for h in headers:
                val = str(r.get(h, ''))
                row_str += f" {val:<{widths[h]}} │"
            print(row_str)
            
        # Bottom border
        draw_line('└', '─', '┘', '┴')

    def get_inventory_summary(self, format='table'):
        """Prints a summary of instances per profile from local memory."""
        if not os.path.exists(CACHE_FILE):
            return "Error: Local memory not found. Please run 'refresh' first."

        with open(CACHE_FILE, 'r') as f:
            memory = json.load(f)

        raw_data = memory.get('raw_data', [])
        summary = {}
        for i in raw_data:
            p = i.get('__Assistant_Profile', 'Unknown')
            summary[p] = summary.get(p, 0) + 1

        if not summary:
            return "No data found in memory."

        if format == 'rich' or format == 'pro':
            print("\n" + "═"*60)
            print(f"  AWS INVENTORY SUMMARY ({len(raw_data)} Instances)")
            print("═"*60)
            for k, v in sorted(summary.items(), key=lambda x: x[1], reverse=True):
                print(f" ║ {k:<45} ║ {v:>4} ║")
            print("═"*60)
            return ""

        sorted_summary = [{"Count": str(v), "Profile": k} for k, v in sorted(summary.items(), key=lambda x: x[1], reverse=True)]
        
        self._print_box_table(sorted_summary)
        return f"\nTotal Instances: {len(raw_data)}"

    def sso_login(self, profile):
        """Triggers the interactive AWS SSO login flow."""
        try:
            print(f"Opening browser for SSO login (Profile: {profile})...")
            # Using subprocess.run without capture_output to allow it to be interactive if needed
            subprocess.run(["aws", "sso", "login", "--profile", profile], check=True)
            return f"Success: Logged in to profile '{profile}'."
        except Exception as e:
            return f"Error during login: {e}"

    def search_memory(self, query, profile=None):
        """Searches local memory for an IP, Name, or Instance ID."""
        if not os.path.exists(CACHE_FILE):
            return {"error": "Local memory not found. Please run 'refresh' first."}

        with open(CACHE_FILE, 'r') as f:
            memory = json.load(f)

        query = query.lower()
        matches = []
        for inst in memory.get('raw_data', []):
            if profile and inst.get('__Assistant_Profile') != profile:
                continue
                
            tags = {t['Key'].lower(): t['Value'] for t in inst.get('Tags', [])}
            name = tags.get('name', '').lower()
            private_ip = str(inst.get('PrivateIpAddress', '')).lower()
            instance_id = inst.get('InstanceId', '').lower()

            # Match if query is in Name, matches IP exactly, or matches ID exactly
            if query in name or query == private_ip or query == instance_id:
                matches.append(inst)

        if not matches:
            print(f"No matches found for '{query}'.")
            return ""

        # SINGLE MATCH: Show detailed "Notepad" style output
        if len(matches) == 1:
            inst = matches[0]
            tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
            print("\n" + "═"*60)
            print(f"  DETAILED INSTANCE VIEW: {tags.get('Name', 'N/A')}")
            print("═"*60)
            print(f"  Instance ID    : {inst.get('InstanceId')}")
            print(f"  Private IP     : {inst.get('PrivateIpAddress', 'N/A')}")
            print(f"  Public IP      : {inst.get('PublicIpAddress', 'N/A')}")
            print(f"  Instance Type  : {inst.get('InstanceType')}")
            print(f"  State          : {inst.get('State', {}).get('Name')}")
            print(f"  VPC ID         : {inst.get('VpcId')}")
            print(f"  Subnet ID      : {inst.get('SubnetId')}")
            print(f"  Launch Time    : {inst.get('LaunchTime')}")
            print(f"  Platform       : {inst.get('PlatformDetails')}")
            print(f"  IAM Role       : {inst.get('IamInstanceProfile', {}).get('Arn', 'N/A').split('/')[-1]}")
            print(f"  Profile (AWS)  : {inst.get('__Assistant_Profile')}")
            print(f"  Region         : {inst.get('__Assistant_Region')}")
            print(f"  SSM Status     : {inst.get('__Assistant_SSM_PingStatus', 'N/A')}")
            print("-" * 60)
            print("  TAGS:")
            for k, v in tags.items():
                print(f"    {k:<15}: {v}")
            print("═"*60 + "\n")
            return ""

        # MULTIPLE MATCHES: Show table
        print(f"\nFound {len(matches)} matches (Showing top 20):")
        
        rows = []
        for m in matches[:20]:
            name = next((t['Value'] for t in m.get('Tags', []) if t['Key'] == 'Name'), 'N/A')[:25]
            rows.append({
                "Name": name,
                "InstanceId": m.get('InstanceId'),
                "PrivateIP": m.get('PrivateIpAddress', 'N/A'),
                "Profile": m.get('__Assistant_Profile')
            })
        
        self._print_box_table(rows)
        return ""

    def query_inventory(self, profile, category, region=None, format='table'):
        """Prints formatted details of inventory details to the terminal."""
        if not os.path.exists(CACHE_FILE):
            return "Error: Local memory not found. Please run 'refresh' first."

        with open(CACHE_FILE, 'r') as f:
            memory = json.load(f)

        instances = [i for i in memory.get('raw_data', []) if i.get('__Assistant_Profile') == profile]
        if region:
            instances = [i for i in instances if i.get('__Assistant_Region') == region]

        if not instances:
            return f"No instances found for profile '{profile}'" + (f" in region '{region}'" if region else "") + "."

        if format == 'list':
            # ... vertical display ...
            print(f"\nACCOUNT: {profile} | REGION: {region if region else 'All'}")
            print("═"*60)
            for idx, inst in enumerate(instances[:50], 1):
                tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                name = tags.get('Name', 'N/A')
                print(f"[{idx:02}] NAME: {name}")
                print(f"     ID: {inst.get('InstanceId')} | IP: {inst.get('PrivateIpAddress', 'N/A')} | TYPE: {inst.get('InstanceType')}")
                print(f"     STATE: {inst.get('State', {}).get('Name')} | SSM: {inst.get('__Assistant_SSM_PingStatus', 'N/A')} | REGION: {inst.get('__Assistant_Region')}")
                print("-" * 60)
            if len(instances) > 50:
                print(f" * Showing 50 of {len(instances)} instances. Use Export for full details.")
            return ""

        if format == 'pro':
            # DEFINITION OF COLUMNS PER CATEGORY
            col_defs = {
                'overview': [('NAME', 30), ('INSTANCE ID', 20), ('PRIVATE IP', 15), ('TYPE', 12), ('STATE', 10), ('SSM STATUS', 12)],
                'network':  [('NAME', 25), ('VPC ID', 20), ('SUBNET ID', 20), ('SECURITY GROUPS', 35)],
                'security': [('NAME', 25), ('INSTANCE ID', 20), ('IAM ROLE', 30), ('PLATFORM', 20)],
                'tags':     [('NAME', 25), ('PROJECT', 20), ('OWNER', 20), ('ENVIRONMENT', 15)]
            }
            
            active_cols = col_defs.get(category, col_defs['overview'])
            
            # Helper to build border lines
            def get_line(left, mid, right, cross):
                line = left
                for i, (_, width) in enumerate(active_cols):
                    line += '═' * (width + 2)
                    if i < len(active_cols) - 1: line += cross
                return line + right

            top    = get_line('╔', '═', '╗', '╦')
            sep    = get_line('╠', '═', '╣', '╬')
            bottom = get_line('╚', '═', '╝', '╩')

            header = "║"
            for label, width in active_cols:
                header += f" {label:<{width}} ║"

            print(f"\nACCOUNT: {profile} | REGION: {region if region else 'All'}")
            print(top)
            print(header)
            print(sep)

            for inst in instances[:20]:
                tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
                name = tags.get('Name', 'N/A')
                
                row = "║"
                for label, width in active_cols:
                    val = "N/A"
                    if label == 'NAME': val = name
                    elif label == 'INSTANCE ID': val = inst.get('InstanceId')
                    elif label == 'PRIVATE IP': val = inst.get('PrivateIpAddress')
                    elif label == 'TYPE': val = inst.get('InstanceType')
                    elif label == 'STATE': val = inst.get('State', {}).get('Name')
                    elif label == 'SSM STATUS': val = inst.get('__Assistant_SSM_PingStatus', 'N/A')
                    elif label == 'VPC ID': val = inst.get('VpcId')
                    elif label == 'SUBNET ID': val = inst.get('SubnetId')
                    elif label == 'SECURITY GROUPS': val = ", ".join([sg.get('GroupName') for sg in inst.get('SecurityGroups', [])])
                    elif label == 'IAM ROLE': val = inst.get('IamInstanceProfile', {}).get('Arn', 'N/A').split('/')[-1]
                    elif label == 'PLATFORM': val = inst.get('PlatformDetails')
                    elif label == 'PROJECT': val = tags.get('Project', tags.get('project', 'N/A'))
                    elif label == 'OWNER': val = tags.get('Owner', tags.get('owner', 'N/A'))
                    elif label == 'ENVIRONMENT': val = tags.get('Environment', tags.get('environment', 'N/A'))
                    
                    val = str(val)[:width] # TRUNCATE
                    row += f" {val:<{width}} ║"
                print(row)
            
            print(bottom)
            if len(instances) > 20:
                print(f" * Showing 20 of {len(instances)} instances. Use Export for full details.")
            return ""

        # PREPARE ROWS FOR TABLE/BOX FORMAT
        rows = []
        for inst in instances:
            tags = {t['Key']: t['Value'] for t in inst.get('Tags', [])}
            name = tags.get('Name', 'N/A')
            
            if category == 'overview':
                rows.append({
                    "Name": name[:35],
                    "InstanceId": inst.get('InstanceId'),
                    "State": inst.get('State', {}).get('Name'),
                    "PrivateIP": inst.get('PrivateIpAddress', 'N/A'),
                    "Type": inst.get('InstanceType'),
                    "SSM": inst.get('__Assistant_SSM_PingStatus', 'N/A')
                })
            elif category == 'network':
                sgs = ", ".join([sg.get('GroupName') for sg in inst.get('SecurityGroups', [])])[:40]
                rows.append({
                    "Name": name[:25],
                    "VpcId": inst.get('VpcId'),
                    "SubnetId": inst.get('SubnetId'),
                    "SGs": sgs
                })
            elif category == 'security':
                iam = inst.get('IamInstanceProfile', {}).get('Arn', 'N/A').split('/')[-1]
                rows.append({
                    "Name": name[:30],
                    "InstanceId": inst.get('InstanceId'),
                    "IAMRole": iam[:25],
                    "Platform": inst.get('PlatformDetails')[:20]
                })
            elif category == 'tags':
                proj = tags.get('Project', tags.get('project', 'N/A'))
                owner = tags.get('Owner', tags.get('owner', 'N/A'))
                env = tags.get('Environment', tags.get('environment', 'N/A'))
                rows.append({
                    "Name": name[:30],
                    "Project": proj[:20],
                    "Owner": owner[:20],
                    "Env": env[:15]
                })

        if not rows:
            return f"No data to display for category '{category}'."

        limit = 30 if format == 'box' else 10
        print(f"\nACCOUNT: {profile} | REGION: {region if region else 'All'}")
        self._print_box_table(rows[:limit])
        
        if len(rows) > limit:
            print(f"\n* Showing top {limit} of {len(rows)}. Use Export to see full list.*")
        return ""

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
    parser.add_argument("command", choices=["refresh", "list-profiles", "discover-accounts", "discover-roles", "discover-all-mappings", "add-profile", "bulk-add", "delete-profile", "export-csv", "summary", "query", "login", "search"])
    parser.add_argument("--profile", help="AWS Profile name")
    parser.add_argument("--account-id", help="AWS Account ID for role discovery")
    parser.add_argument("--category", choices=["overview", "network", "security", "tags"], help="Category for CSV export or Query")
    parser.add_argument("--output", help="Output path for CSV file")
    parser.add_argument("--query-term", dest="query_term", help="Search query (IP, Name, or ID)")
    # Args for add-profile and bulk-add
    parser.add_argument("--name")
    parser.add_argument("--url")
    parser.add_argument("--sso-region")
    parser.add_argument("--role")
    parser.add_argument("--region")
    parser.add_argument("--mappings", help="JSON string of mappings for bulk-add")
    parser.add_argument("--format", choices=["table", "rich", "pro", "list", "box"], default="table", help="Output format")

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
    elif args.command == "discover-all-mappings":
        print(json.dumps(engine.discover_all_sso_mappings(args.profile), indent=2))
    elif args.command == "add-profile":
        print(engine.add_profile(args.name, args.url, args.sso_region, args.account_id, args.role, args.region))
    elif args.command == "bulk-add":
        print(engine.bulk_add_profiles(args.mappings, args.url, args.sso_region, args.region))
    elif args.command == "delete-profile":
        print(engine.delete_profile(args.name))
    elif args.command == "export-csv":
        print(engine.export_csv(args.profile, args.category, args.output))
    elif args.command == "summary":
        print(engine.get_inventory_summary(format=args.format))
    elif args.command == "query":
        print(engine.query_inventory(args.profile, args.category, args.region, format=args.format))
    elif args.command == "login":
        print(engine.sso_login(args.profile))
    elif args.command == "search":
        print(engine.search_memory(args.query_term, profile=args.profile))
