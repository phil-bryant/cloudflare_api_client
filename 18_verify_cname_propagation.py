#!/usr/bin/env python3

# #authored-by-ai #gemini-2.5-pro #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that a CNAME record has propagated to public DNS servers
and is correctly configured in Cloudflare.

Reads the record details from 17.output.record_details.json.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN

Usage:
  ./18_verify_cname_propagation.py <zone_domain>
  ./18_verify_cname_propagation.py example.com
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
SCRIPT_NUM = "18"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_DETAILS_FILE = "17.output.record_details.json"
OUTPUT_VERIFICATION_FILE = f"{OUTPUT_PREFIX}verification_result.json"

# Public DNS servers to query
DNS_SERVERS = [
    ('8.8.8.8', 'Google DNS'),
    ('1.1.1.1', 'Cloudflare DNS'),
    ('9.9.9.9', 'Quad9 DNS')
]

# Clean up old output files at startup
def cleanup_old_output_files():
    """Move previous output files to ~/.Trash"""
    trash_dir = os.path.expanduser("~/.Trash")
    if not os.path.exists(trash_dir):
        os.makedirs(trash_dir, exist_ok=True)
    
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
    dotenv_path = os.path.join(os.path.expanduser("~"), ".env")
    load_dotenv(dotenv_path=dotenv_path)
    
    required_vars = ["CLOUDFLARE_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables for Cloudflare API: {', '.join(missing_vars)}")
        print("Cloudflare API verification will be skipped")
        return {}
    
    # Need Zone ID too for Cloudflare verification
    if not os.getenv("CLOUDFLARE_ZONE_ID"):
         print("Warning: Missing CLOUDFLARE_ZONE_ID environment variable.")
         print("Cloudflare API verification will be skipped")
         return {"api_token": os.getenv("CLOUDFLARE_API_TOKEN")}

    return {
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN"),
        "zone_id": os.getenv("CLOUDFLARE_ZONE_ID")
    }

def read_record_details_from_file(file_path):
    """
    Read CNAME record details from the specified file.
    
    Args:
        file_path (str): Path to the input file (e.g., 17.output.record_details.json).
        
    Returns:
        dict: Dictionary containing the CNAME record details or None on error.
    """
    try:
        print(f"Reading CNAME record details from: {file_path}")
        with open(file_path, 'r') as f:
            record_data = json.load(f)
            
        # Validate required fields for CNAME verification
        required = ['record_name', 'record_content', 'record_type', 'record_id']
        if not all(key in record_data for key in required) or record_data.get('record_type') != 'CNAME':
            print("Error: Input file missing required CNAME fields or is not a CNAME record.")
            print(f"Required fields: {required}")
            return None
            
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

def verify_record_in_cloudflare(zone_id, api_token, record_id, expected_details):
    """
    Verify that the CNAME record exists in Cloudflare with the correct values.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to verify.
        expected_details (dict): The expected details of the record from the input file.
        
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
        
        # Compare relevant fields
        if record.get('type') != 'CNAME':
            print(f"❌ Record type mismatch: Expected CNAME, got {record.get('type')}")
            return False
            
        # Normalize names (e.g., remove trailing dot if present)
        cf_name = record.get('name', '').rstrip('.')
        expected_name = expected_details.get('record_name', '').rstrip('.')
        if cf_name.lower() != expected_name.lower():
            print(f"❌ Record name mismatch: Expected {expected_name}, got {cf_name}")
            return False

        # Normalize content (target)
        cf_content = record.get('content', '').rstrip('.')
        expected_content = expected_details.get('record_content', '').rstrip('.')
        if cf_content.lower() != expected_content.lower():
            print(f"❌ Record content mismatch: Expected {expected_content}, got {cf_content}")
            return False
        
        print(f"✅ Record found in Cloudflare with matching values:")
        print(f"  Type: {record.get('type')}")
        print(f"  Name: {record.get('name')}")
        print(f"  Content: {record.get('content')}")
        return True
    except Exception as e:
        print(f"Error verifying record in Cloudflare: {e}")
        return False

def query_cname_in_public_dns(record_name, expected_target):
    """
    Query public DNS servers for the CNAME record and verify its target.
    
    Args:
        record_name (str): The full CNAME record name (e.g., 'api.example.com').
        expected_target (str): The expected target hostname.
        
    Returns:
        bool: True if the CNAME resolves correctly on at least one server, False otherwise.
    """
    print(f"\n📡 Querying public DNS for CNAME record: {record_name}")
    print(f"   Expected Target: {expected_target}")
    
    # Normalize expected target (lowercase, remove trailing dot)
    normalized_expected_target = expected_target.lower().rstrip('.')
    
    found_correctly = False
    
    for server_ip, server_name in DNS_SERVERS:
        try:
            print(f"   Querying {server_name} ({server_ip})...")
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [server_ip]
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(record_name, 'CNAME')
            
            if not answers:
                print(f"     No CNAME answer from {server_name}")
                continue
                
            # Process all answers, though usually there's only one CNAME target
            server_matched = False
            for rdata in answers:
                actual_target = str(rdata.target).rstrip('.')
                print(f"     Found target: {actual_target}")
                
                # Compare normalized target
                if actual_target.lower() == normalized_expected_target:
                    print(f"     ✅ Match found on {server_name}!")
                    server_matched = True
                    found_correctly = True # Mark as found correctly on at least one server
                    # break # Optional: stop checking this server if match found
                else:
                     print(f"     ❌ Target mismatch on {server_name} (Expected: {normalized_expected_target})")
            
            if not server_matched:
                print(f"     No matching CNAME target found on {server_name}")

        except dns.resolver.NoAnswer:
            print(f"     No CNAME record found for {record_name} via {server_name}")
        except dns.resolver.NXDOMAIN:
            print(f"     Domain {record_name} does not exist according to {server_name}")
        except dns.exception.Timeout:
             print(f"     Query timed out for {server_name}")
        except Exception as e:
            print(f"     Error querying {server_name}: {e}")
            
    if not found_correctly:
        print(f"❌ CNAME record for {record_name} did not resolve to {expected_target} on any queried public DNS server.")
        
    return found_correctly

if __name__ == "__main__":
    cleanup_old_output_files()
    
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <zone_domain>")
        print("Example: ./18_verify_cname_propagation.py example.com")
        print("(Reads details from 17.output.record_details.json)")
        sys.exit(1)
        
    zone_domain_arg = sys.argv[1] # Used for context, actual name read from file
    env = load_env()
    
    print(f"--- Verifying CNAME Propagation for records related to {zone_domain_arg} ---")

    # Read record details from the input file
    record_details = read_record_details_from_file(INPUT_RECORD_DETAILS_FILE)
    
    if not record_details:
        print("❌ Cannot proceed without valid CNAME record details.")
        sys.exit(1)
    
    record_name = record_details['record_name']
    expected_target = record_details['record_content']
    record_id = record_details['record_id']

    # Verify in Cloudflare (if credentials available)
    cloudflare_verified = False
    if env and 'api_token' in env and 'zone_id' in env:
        cloudflare_verified = verify_record_in_cloudflare(
            env['zone_id'], env['api_token'], record_id, record_details
        )
    else:
        print("\n⚠️ Cloudflare API verification skipped due to missing credentials or Zone ID.")
    
    # Verify in public DNS
    dns_propagated = query_cname_in_public_dns(record_name, expected_target)
    
    # Save verification results
    verification_results = {
        "timestamp": record_details.get("timestamp"), # Use timestamp from input file
        "zone_domain": record_details.get("zone_domain"),
        "record_name": record_name,
        "record_type": "CNAME",
        "expected_target": expected_target,
        "cloudflare_verified": cloudflare_verified,
        "dns_propagated": dns_propagated
    }
    
    try:
        with open(OUTPUT_VERIFICATION_FILE, 'w') as f:
            json.dump(verification_results, f, indent=2)
        print(f"\nVerification results saved to {OUTPUT_VERIFICATION_FILE}")
    except Exception as e:
         print(f"\nError saving verification results: {e}")

    # print("\n--- Verification Summary ---")
    # print(f"Record: {record_name}")
    # print(f"Target: {expected_target}")
    # 
    # if cloudflare_verified:
    #     print("✅ Cloudflare: Record correctly configured")
    # else:
    #     print("❌ Cloudflare: Record missing, incorrect, or verification skipped")
    # 
    # if dns_propagated:
    #     print("✅ Public DNS: Record propagated correctly to at least one major resolver")
    # else:
    #     print("❌ Public DNS: Record not found or incorrect on queried resolvers (may need more time)")

    # Exit code reflects propagation status primarily
    sys.exit(0 if dns_propagated else 1) 