#!/usr/bin/env python3

# #authored-by-ai #gemini-2.5-pro #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that an A record (typically for Vercel web deployment)
has propagated to public DNS servers. Optionally verifies against Cloudflare API if details allow.

Reads the record details from 15.output.verification_results.json.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID (Optional, needed for Cloudflare API check)

Usage:
  ./16_verify_vercel_web_propagation.py <zone_domain>
  ./16_verify_vercel_web_propagation.py example.com
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
SCRIPT_NUM = "16"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_DETAILS_FILE = "15.output.verification_results.json" # Input from Vercel config script
INPUT_RECORD_ID_FILE = "15.output.record_id.txt" # Input file containing the record ID
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
    
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    zone_id = os.getenv("CLOUDFLARE_ZONE_ID")
    
    env_vars = {}
    if api_token:
        env_vars["api_token"] = api_token
    else:
        print("Warning: Missing CLOUDFLARE_API_TOKEN. Cloudflare API check requires it.")

    if zone_id:
        env_vars["zone_id"] = zone_id
    else:
         print("Warning: Missing CLOUDFLARE_ZONE_ID. Cloudflare API check requires it.")
    
    if "api_token" not in env_vars or "zone_id" not in env_vars:
         print("Cloudflare API verification will be skipped due to missing credentials.")

    return env_vars

def read_record_details_from_file(file_path):
    """
    Read A record details from the specified file (15.output.verification_results.json).
    
    Args:
        file_path (str): Path to the input file (e.g., 15.output.verification_results.json).
        
    Returns:
        dict: Dictionary containing the A record details or None on error.
              Expected keys in output dict: 'record_name', 'expected_content', 'record_type', 'record_id' (optional)
    """
    try:
        print(f"Reading A record details from: {file_path}")
        with open(file_path, 'r') as f:
            record_data = json.load(f)
            
        # Validate required fields from 15.output.verification_results.json format
        required_input = ['record_name', 'expected_content', 'record_type']
        if not all(key in record_data for key in required_input) or record_data.get('record_type') != 'A':
            print(f"Error: Input file {file_path} missing required fields or is not an A record.")
            print(f"Required input fields: {required_input}, Type: A")
            print(f"Found keys: {list(record_data.keys())}")
            return None

        # Map to expected output format for this script
        details = {
            "record_name": record_data['record_name'],
            "expected_ip": record_data['expected_content'], # Map expected_content to expected_ip
            "record_type": record_data['record_type'],
            "record_id": record_data.get('record_id'), # Get record_id if it exists, otherwise None
            "zone_domain": record_data.get('domain'), # Get domain if it exists
            "timestamp": record_data.get("timestamp") # Get timestamp if it exists
        }
            
        return details
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
    Verify that the A record exists in Cloudflare with the correct values, if record_id is provided.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to verify (can be None).
        expected_details (dict): The expected details ('record_name', 'expected_ip').
        
    Returns:
        bool or None: True if verified, False if mismatch/not found, None if verification skipped (no record_id).
    """
    if not record_id:
        print("\n☁️ Skipping Cloudflare API verification: Record ID not found in input file.")
        return None # Indicate skipped verification
        
    try:
        print(f"\n☁️ Verifying record in Cloudflare (ID: {record_id})...")
        
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
        
        # Compare relevant fields for A record
        if record.get('type') != 'A':
            print(f"❌ Record type mismatch: Expected A, got {record.get('type')}")
            return False
            
        # Normalize names (e.g., remove trailing dot if present)
        cf_name = record.get('name', '').rstrip('.')
        expected_name = expected_details.get('record_name', '').rstrip('.')
        if cf_name.lower() != expected_name.lower():
            print(f"❌ Record name mismatch: Expected {expected_name}, got {cf_name}")
            return False

        # Compare content (IP address)
        cf_content = record.get('content', '')
        expected_ip = expected_details.get('expected_ip', '') # Use expected_ip now
        if cf_content != expected_ip:
            print(f"❌ Record content mismatch: Expected IP {expected_ip}, got {cf_content}")
            return False
        
        print(f"✅ Record found in Cloudflare with matching values:")
        print(f"  Type: {record.get('type')}")
        print(f"  Name: {record.get('name')}")
        print(f"  Content (IP): {record.get('content')}")
        return True
    except Exception as e:
        print(f"Error verifying record in Cloudflare: {e}")
        return False # Treat errors during API check as verification failure

def query_a_record_in_public_dns(record_name, expected_ip):
    """
    Query public DNS servers for the A record and verify its IP address.
    
    Args:
        record_name (str): The full record name (e.g., 'example.com').
        expected_ip (str): The expected IP address.
        
    Returns:
        bool: True if the A record resolves correctly on at least one server, False otherwise.
    """
    print(f"\n📡 Querying public DNS for A record: {record_name}")
    print(f"   Expected IP: {expected_ip}")
    
    found_correctly = False
    
    for server_ip, server_name in DNS_SERVERS:
        try:
            print(f"   Querying {server_name} ({server_ip})...")
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [server_ip]
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(record_name, 'A')
            
            if not answers:
                print(f"     No A record answer from {server_name}")
                continue
                
            # Process all answers (IP addresses)
            server_matched = False
            for rdata in answers:
                actual_ip = rdata.address
                print(f"     Found IP: {actual_ip}")
                
                # Compare IP address
                if actual_ip == expected_ip:
                    print(f"     ✅ Match found on {server_name}!")
                    server_matched = True
                    found_correctly = True # Mark as found correctly on at least one server
                    # break # Optional: stop checking this server if match found
                else:
                     print(f"     ❌ IP mismatch on {server_name} (Expected: {expected_ip})")
            
            if not server_matched:
                print(f"     No matching A record IP found on {server_name}")

        except dns.resolver.NoAnswer:
            print(f"     No A record found for {record_name} via {server_name}")
        except dns.resolver.NXDOMAIN:
            print(f"     Domain {record_name} does not exist according to {server_name}")
        except dns.exception.Timeout:
             print(f"     Query timed out for {server_name}")
        except Exception as e:
            print(f"     Error querying {server_name}: {e}")
            
    if not found_correctly:
        print(f"❌ A record for {record_name} did not resolve to {expected_ip} on any queried public DNS server.")
        
    return found_correctly

if __name__ == "__main__":
    cleanup_old_output_files()
    
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <zone_domain>")
        print("Example: ./16_verify_vercel_web_propagation.py example.com")
        print("(Reads details from 15.output.verification_results.json)")
        sys.exit(1)
        
    zone_domain_arg = sys.argv[1] # Used for user feedback, actual name read from file
    env = load_env()
    
    print(f"--- Verifying Vercel A Record Propagation for {zone_domain_arg} ---")

    # Read record details from the input file
    record_details = read_record_details_from_file(INPUT_RECORD_DETAILS_FILE)
    
    if not record_details:
        print("❌ Cannot proceed without valid A record details from script 15's output file.")
        sys.exit(1)
    
    # Attempt to read record_id from the separate file
    record_id = None
    try:
        with open(INPUT_RECORD_ID_FILE, 'r') as f:
            record_id = f.read().strip()
        if record_id:
            print(f"Found record ID in {INPUT_RECORD_ID_FILE}: {record_id}")
            # Add the record_id to the details dictionary if found
            record_details['record_id'] = record_id
        else:
            print(f"Warning: {INPUT_RECORD_ID_FILE} exists but is empty.")
    except FileNotFoundError:
        print(f"Info: Record ID file ({INPUT_RECORD_ID_FILE}) not found. Cloudflare API check requires it.")
    except Exception as e:
        print(f"Error reading record ID from {INPUT_RECORD_ID_FILE}: {e}")

    # Extract details needed for verification
    record_name = record_details['record_name']
    expected_ip = record_details['expected_ip'] # Use the mapped key
    # record_id is now read from the file above, or remains None
    record_id = record_details.get('record_id') # Re-fetch from dict, might be None

    # Verify in Cloudflare (if credentials and record_id available)
    cloudflare_verified = None # Default to skipped/unknown
    if env and 'api_token' in env and 'zone_id' in env and record_id:
        cloudflare_verified = verify_record_in_cloudflare(
            env['zone_id'], env['api_token'], record_id, record_details
        )
    elif not record_id:
        # Specific message for missing record_id (file not found or empty)
        print("⚪ Cloudflare API verification skipped: Record ID was not found in "
              f"{INPUT_RECORD_DETAILS_FILE} or {INPUT_RECORD_ID_FILE}.")
    else: # Missing credentials case
        print("⚠️ Cloudflare API verification skipped due to missing credentials (CLOUDFLARE_API_TOKEN or CLOUDFLARE_ZONE_ID).")
    
    # Verify in public DNS
    dns_propagated = query_a_record_in_public_dns(record_name, expected_ip)
    
    # Save verification results
    verification_results = {
        "timestamp": record_details.get("timestamp"), # Use timestamp from input file if available
        "zone_domain": record_details.get("zone_domain", zone_domain_arg), # Use domain from file or arg
        "record_name": record_name,
        "record_type": "A", # Explicitly state type being verified
        "expected_ip": expected_ip,
        "cloudflare_verified": cloudflare_verified, # Can be True, False, or None
        "dns_propagated": dns_propagated
    }
    
    try:
        with open(OUTPUT_VERIFICATION_FILE, 'w') as f:
            json.dump(verification_results, f, indent=2)
        print(f"\nVerification results saved to {OUTPUT_VERIFICATION_FILE}")
    except Exception as e:
         print(f"\nError saving verification results: {e}")

    # print("\n--- Verification Summary ---")
    # print(f"Record: {record_name} (Type A)")
    # print(f"Expected IP: {expected_ip}")
    # 
    # if cloudflare_verified is True:
    #     print("✅ Cloudflare API: Record correctly configured")
    # elif cloudflare_verified is False:
    #     print("❌ Cloudflare API: Record missing, incorrect, or API error occurred")
    # else: # cloudflare_verified is None
    #     print("⚪ Cloudflare API: Verification skipped (missing Record ID or credentials)")
    # 
    # if dns_propagated:
    #     print("✅ Public DNS: Record propagated correctly to at least one major resolver")
    # else:
    #     print("❌ Public DNS: Record not found or incorrect on queried resolvers (may need more time)")

    # Exit code reflects propagation status primarily
    sys.exit(0 if dns_propagated else 1) 