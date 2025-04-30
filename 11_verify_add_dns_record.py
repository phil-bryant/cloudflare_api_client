#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that a DNS record was correctly added using the Cloudflare API.
Takes the domain as a command line argument.
Reads the record ID from 10.output.record_id.txt and the record details from 09.output.record_details.json.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./11_verify_add_dns_record.py yourdomain.com
  ./11_verify_add_dns_record.py yourdomain.com <source_script_num>
"""

import os
import sys
import json
import dns.resolver
import requests
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "11"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_ID_FILE = "10.output.record_id.txt"
INPUT_RECORD_DETAILS_FILE = "09.output.record_details.json"
OUTPUT_VERIFICATION_FILE = f"{OUTPUT_PREFIX}verification_results.json"

# Clean up old output files at startup
def cleanup_old_output_files():
    """Move previous output files to ~/.Trash"""
    trash_dir = os.path.expanduser("~/.Trash")
    if not os.path.exists(trash_dir):
        os.makedirs(trash_dir, exist_ok=True)
    
    # Find all files matching the pattern
    old_files = glob.glob(f"{OUTPUT_PREFIX}*")
    
    if old_files:
        print(f"Moving {len(old_files)} old output files to ~/.Trash")
        for file in old_files:
            try:
                shutil.move(file, os.path.join(trash_dir, file))
                print(f"  Moved {file}")
            except Exception as e:
                print(f"  Error moving {file}: {e}")

def load_env():
    """Load environment variables from .env file."""
    # Look for .env in the home directory
    dotenv_path = os.path.join(os.path.expanduser("~"), ".env")
    load_dotenv(dotenv_path=dotenv_path)
    
    required_vars = ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables for Cloudflare API: {', '.join(missing_vars)}")
        print("Cloudflare API verification will be skipped")
        return {}
    
    return {
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN"),
        "zone_id": os.getenv("CLOUDFLARE_ZONE_ID")
    }

def read_record_id_from_file(file_path):
    """
    Read the record ID from the specified file.
    
    Args:
        file_path (str): Path to the input file.
        
    Returns:
        str: The record ID or None if not found.
    """
    try:
        print(f"Reading record ID from: {file_path}")
        with open(file_path, 'r') as f:
            record_id = f.read().strip()
            
        if not record_id:
            print("Error: Empty record ID in file.")
            return None
            
        return record_id
    except FileNotFoundError:
        print(f"Error: Record ID file not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading record ID file: {e}")
        return None

def read_record_details_from_file(file_path):
    """
    Read DNS record details from the specified file.
    
    Args:
        file_path (str): Path to the input file.
        
    Returns:
        dict: Dictionary containing the DNS record details.
    """
    try:
        print(f"Reading DNS record details from: {file_path}")
        with open(file_path, 'r') as f:
            record_data = json.load(f)
            
        return record_data
    except FileNotFoundError:
        print(f"Error: Record details file not found at {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file: {e}")
        return None
    except Exception as e:
        print(f"Error reading or parsing record details file: {e}")
        return None

def verify_record_in_cloudflare(domain, zone_id, api_token, record_id, record_details):
    """
    Verify that the record exists in Cloudflare with the correct values.
    
    Args:
        domain (str): The domain name.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to verify.
        record_details (dict): The expected details of the record.
        
    Returns:
        bool: True if the record exists with the correct values, False otherwise.
    """
    try:
        print(f"\n☁️ Verifying record in Cloudflare...")
        
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 404:
            print(f"❌ Record with ID {record_id} not found in Cloudflare")
            return False
            
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            error_msg = data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"❌ Cloudflare API error: {error_msg}")
            return False
        
        record = data.get('result', {})
        
        # Check that the record matches the expected values
        if record.get('type') != record_details.get('type'):
            print(f"❌ Record type mismatch: Expected {record_details.get('type')}, got {record.get('type')}")
            return False
            
        if record.get('name') != record_details.get('name'):
            print(f"❌ Record name mismatch: Expected {record_details.get('name')}, got {record.get('name')}")
            return False
            
        # Special handling for SRV records
        if record_details.get('type') == 'SRV':
            # In Cloudflare, SRV content is formatted as "weight port target"
            # Extract just the target (domain) part for comparison
            cloudflare_content = record.get('content', '')
            
            # Extract the target from the content (the last part)
            parts = cloudflare_content.split()
            if len(parts) >= 3:  # We expect at least 3 parts: weight, port, target
                actual_target = parts[-1]  # The last part is the target
                expected_target = record_details.get('content')
                
                if actual_target.lower() != expected_target.lower():
                    print(f"❌ SRV target mismatch: Expected {expected_target}, got {actual_target}")
                    return False
                
                # Also check priority, weight, port if available
                if 'priority' in record_details and record.get('priority') != record_details.get('priority'):
                    print(f"❌ SRV priority mismatch: Expected {record_details.get('priority')}, got {record.get('priority')}")
                    return False
                
                # For weight, it's in the content string
                if 'weight' in record_details:
                    actual_weight = int(parts[0])
                    expected_weight = record_details.get('weight')
                    if actual_weight != expected_weight:
                        print(f"❌ SRV weight mismatch: Expected {expected_weight}, got {actual_weight}")
                        return False
                
                # For port, it's in the content string
                if 'port' in record_details:
                    actual_port = int(parts[1])
                    expected_port = record_details.get('port')
                    if actual_port != expected_port:
                        print(f"❌ SRV port mismatch: Expected {expected_port}, got {actual_port}")
                        return False
                        
                print(f"✅ SRV record found in Cloudflare with matching target: {actual_target}")
                print(f"  Full SRV content: {cloudflare_content}")
            else:
                print(f"❌ Invalid SRV content format: {cloudflare_content}")
                return False
        else:
            # Regular content matching for non-SRV records
            if record.get('content') != record_details.get('content'):
                print(f"❌ Record content mismatch: Expected {record_details.get('content')}, got {record.get('content')}")
                return False
                
            # Check priority for MX records
            if record_details.get('type') == 'MX' and "priority" in record_details:
                if record.get('priority') != record_details.get('priority'):
                    print(f"❌ MX priority mismatch: Expected {record_details.get('priority')}, got {record.get('priority')}")
                    return False
        
        print(f"✅ Record found in Cloudflare with matching values:")
        print(f"  Type: {record.get('type')}")
        print(f"  Name: {record.get('name')}")
        print(f"  Content: {record.get('content')}")
        print(f"  TTL: {record.get('ttl')}")
        
        if 'priority' in record:
            print(f"  Priority: {record.get('priority')}")
            
        return True
    except Exception as e:
        print(f"Error verifying record in Cloudflare: {e}")
        return False

def query_dns_servers(record_type, name):
    """
    Query public DNS servers for the specified record.
    
    Args:
        record_type (str): The type of DNS record (e.g., 'A', 'MX', 'CNAME').
        name (str): The name to query.
        
    Returns:
        list: List of DNS responses.
    """
    # List of public DNS servers to query
    dns_servers = [
        ('8.8.8.8', 'Google DNS'),
        ('1.1.1.1', 'Cloudflare DNS')
    ]
    
    results = []
    
    for server, server_name in dns_servers:
        try:
            print(f"\n📡 Querying {server_name} ({server}) for {record_type} records for {name}...")
            
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [server]
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(name, record_type)
            server_results = []
            
            for rdata in answers:
                if record_type == 'MX':
                    server_results.append((rdata.preference, str(rdata.exchange).rstrip('.')))
                elif record_type == 'SRV':
                    # SRV records have multiple fields
                    priority = rdata.priority
                    weight = rdata.weight
                    port = rdata.port
                    target = str(rdata.target).rstrip('.')
                    
                    # Create a tuple of all SRV data
                    server_results.append((priority, weight, port, target))
                    print(f"  - Priority: {priority}, Weight: {weight}, Port: {port}, Target: {target}")
                elif record_type == 'CNAME':
                    server_results.append(str(rdata.target).rstrip('.'))
                elif record_type == 'TXT':
                    server_results.append(str(rdata).strip('"'))
                else:
                    server_results.append(str(rdata))
                
            results.append((server_name, server_results))
            
            print(f"  Found {len(server_results)} {record_type} records in {server_name}")
            if record_type != 'SRV':  # Already printed SRV details above
                for result in server_results:
                    print(f"  - {result}")
        except dns.resolver.NoAnswer:
            print(f"  No {record_type} records found for {name} via {server_name}")
        except dns.resolver.NXDOMAIN:
            print(f"  Domain {name} does not exist in {server_name}")
        except Exception as e:
            print(f"  Error querying {record_type} records via {server_name}: {e}")
    
    return results

def record_matches_dns_result(record_details, dns_result):
    """
    Check if the record details match a DNS query result.
    
    Args:
        record_details (dict): The expected record details.
        dns_result: The result from a DNS query.
        
    Returns:
        bool: True if the record matches the DNS result, False otherwise.
    """
    record_type = record_details.get('type')
    
    if record_type == 'MX':
        # DNS result for MX is a tuple of (priority, server)
        priority = record_details.get('priority', 0)
        content = record_details.get('content').lower()
        
        # MX records are tuples of (priority, server)
        for mx_record in dns_result:
            if isinstance(mx_record, tuple) and len(mx_record) == 2:
                dns_priority, dns_server = mx_record
                if dns_priority == priority and dns_server.lower() == content:
                    return True
    elif record_type == 'SRV':
        # For SRV records, we just need to match the target (domain)
        expected_target = record_details.get('content').lower()
        expected_priority = record_details.get('priority', 0)
        expected_weight = record_details.get('weight', 0)
        expected_port = record_details.get('port', 0)
        
        # SRV records from DNS are structured differently depending on the library
        for srv_record in dns_result:
            # Check if it's using the dnspython format
            if hasattr(srv_record, 'target'):
                # dnspython SRV record
                target = str(srv_record.target).rstrip('.').lower()
                priority = getattr(srv_record, 'priority', 0)
                weight = getattr(srv_record, 'weight', 0)
                port = getattr(srv_record, 'port', 0)
                
                if (target == expected_target and 
                    priority == expected_priority and 
                    weight == expected_weight and 
                    port == expected_port):
                    return True
            # Or it might be a tuple or string representation
            elif isinstance(srv_record, tuple) and len(srv_record) >= 4:
                # Tuple format: (priority, weight, port, target)
                priority, weight, port, target = srv_record[:4]
                target = target.lower().rstrip('.')
                
                if (target == expected_target and 
                    priority == expected_priority and 
                    weight == expected_weight and 
                    port == expected_port):
                    return True
            elif isinstance(srv_record, str):
                # String format might be "priority weight port target"
                parts = srv_record.split()
                if len(parts) >= 4:
                    try:
                        priority = int(parts[0])
                        weight = int(parts[1])
                        port = int(parts[2])
                        target = ' '.join(parts[3:]).lower().rstrip('.')
                        
                        if (target == expected_target and 
                            priority == expected_priority and 
                            weight == expected_weight and 
                            port == expected_port):
                            return True
                    except (ValueError, IndexError):
                        pass
    elif record_type == 'CNAME':
        # CNAME records are strings
        content = record_details.get('content').lower().rstrip('.')
        
        for cname_record in dns_result:
            if cname_record.lower() == content:
                return True
    elif record_type == 'TXT':
        # TXT records are strings
        content = record_details.get('content')
        
        for txt_record in dns_result:
            if txt_record == content:
                return True
    else:
        # A, AAAA, etc. records are strings
        content = record_details.get('content')
        
        for record in dns_result:
            if record == content:
                return True
    
    return False

def verify_record_in_public_dns(record_details):
    """
    Verify that the record has propagated to public DNS servers.
    
    Args:
        record_details (dict): The expected record details.
        
    Returns:
        bool: True if the record has propagated to public DNS, False otherwise.
    """
    record_type = record_details.get('type')
    name = record_details.get('name')
    
    # Query public DNS servers
    dns_results = query_dns_servers(record_type, name)
    
    if not dns_results:
        print(f"❌ No DNS results from any public DNS servers")
        return False
    
    # Check if any of the DNS results match the expected record
    for server_name, server_results in dns_results:
        if record_matches_dns_result(record_details, server_results):
            print(f"✅ Record found in {server_name} with matching values")
            return True
        else:
            print(f"❌ Record not found in {server_name} with matching values")
    
    return False

if __name__ == "__main__":
    # Clean up old output files at startup
    cleanup_old_output_files()
    
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} <yourdomain.com> [source_script_num]")
        sys.exit(1)

    domain = sys.argv[1]
    env = load_env()
    
    # Check if there's a source script number provided
    source_script_num = None
    if len(sys.argv) == 3:
        source_script_num = sys.argv[2]
        INPUT_RECORD_ID_FILE = f"{source_script_num}.output.record_id.txt"
        INPUT_RECORD_DETAILS_FILE = f"{source_script_num}.output.record_details.json"
        print(f"Using input files from script {source_script_num}")
    
    print(f"--- Verifying DNS Record for {domain} ---")
    
    # Read record ID and details from files
    record_id = read_record_id_from_file(INPUT_RECORD_ID_FILE)
    record_details = read_record_details_from_file(INPUT_RECORD_DETAILS_FILE)
    
    if not record_id or not record_details:
        print("❌ Missing record ID or details. Cannot verify.")
        sys.exit(1)
    
    # Verify in Cloudflare
    cloudflare_verified = False
    if env and 'api_token' in env and 'zone_id' in env:
        cloudflare_verified = verify_record_in_cloudflare(
            domain, env['zone_id'], env['api_token'], record_id, record_details
        )
    else:
        print("❌ Cloudflare API verification skipped due to missing environment variables")
    
    # Verify in public DNS
    dns_verified = verify_record_in_public_dns(record_details)
    
    # Save verification results
    verification_results = {
        "timestamp": os.path.getmtime(INPUT_RECORD_ID_FILE) if os.path.exists(INPUT_RECORD_ID_FILE) else None,
        "domain": domain,
        "record_type": record_details.get('type'),
        "record_name": record_details.get('name'),
        "cloudflare_verified": cloudflare_verified,
        "dns_verified": dns_verified
    }
    
    with open(OUTPUT_VERIFICATION_FILE, 'w') as f:
        json.dump(verification_results, f, indent=2)
    
    print("\n--- Verification Summary ---")
    
    if cloudflare_verified:
        print("✅ Cloudflare: Record correctly configured")
    else:
        print("❌ Cloudflare: Record missing or incorrect")
    
    if dns_verified:
        print("✅ Public DNS: Record correctly propagated")
    else:
        print("❌ Public DNS: Record missing, incorrect, or not yet propagated")
    
    if cloudflare_verified and dns_verified:
        print("\n--- Verification Successful ✅ ---")
        print(f"The {record_details.get('type')} record is correctly configured in both Cloudflare and public DNS.")
        sys.exit(0)
    elif cloudflare_verified:
        print("\n--- Verification Partially Successful ⚠️ ---")
        print("The record is correctly configured in Cloudflare but not yet visible in public DNS.")
        print("DNS propagation may take some time (can take up to 48 hours).")
        sys.exit(0)  # Still exit with success since Cloudflare is correctly configured
    else:
        print("\n--- Verification Failed ❌ ---")
        print("The record is NOT correctly configured.")
        sys.exit(1) 