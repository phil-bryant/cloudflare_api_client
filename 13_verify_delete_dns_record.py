#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that a DNS record was correctly deleted from Cloudflare.
Takes the domain as a command line argument.
Reads the record ID from 09.output.record_id.txt.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./13_verify_delete_dns_record.py yourdomain.com
  ./13_verify_delete_dns_record.py yourdomain.com <source_script_num>
"""

import os
import sys
import requests
import json
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "13"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_ID_FILE = "09.output.record_id.txt"
INPUT_DELETION_RESULT_FILE = "12.output.deletion_result.json"
OUTPUT_VERIFICATION_FILE = f"{OUTPUT_PREFIX}verification_result.json"

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

def verify_record_deleted(zone_id, api_token, record_id):
    """
    Verify that the record was deleted from Cloudflare.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to verify.
        
    Returns:
        bool: True if the record was deleted, False otherwise.
    """
    try:
        print(f"\n☁️ Verifying record deletion in Cloudflare...")
        
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(endpoint, headers=headers)
        
        # If the record is not found, it was successfully deleted
        if response.status_code == 404:
            print(f"✅ Record with ID {record_id} not found in Cloudflare (successfully deleted)")
            return True
        
        # If we get a 200 response, the record still exists
        if response.status_code == 200:
            print(f"❌ Record with ID {record_id} still exists in Cloudflare")
            return False
        
        # For any other response, we can't be sure
        print(f"⚠️ Unexpected response from Cloudflare API: {response.status_code}")
        print(f"Unable to verify record deletion")
        return False
    except Exception as e:
        print(f"Error verifying record deletion: {e}")
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
        INPUT_DELETION_RESULT_FILE = f"{source_script_num}.output.deletion_result.json"
        print(f"Using input files from script {source_script_num}")
    
    print(f"--- Verifying DNS Record Deletion for {domain} ---")
    
    # Read record ID from file
    record_id = read_record_id_from_file(INPUT_RECORD_ID_FILE)
    
    if not record_id:
        print("❌ Missing record ID. Cannot verify deletion.")
        sys.exit(1)
    
    # Verify in Cloudflare
    if env and 'api_token' in env and 'zone_id' in env:
        deletion_verified = verify_record_deleted(env['zone_id'], env['api_token'], record_id)
    else:
        print("❌ Cloudflare API verification skipped due to missing environment variables")
        deletion_verified = False
    
    # Save verification result
    verification_result = {
        "domain": domain,
        "record_id": record_id,
        "deletion_verified": deletion_verified
    }
    
    # Try to read the deletion result file for additional context
    if os.path.exists(INPUT_DELETION_RESULT_FILE):
        try:
            with open(INPUT_DELETION_RESULT_FILE, 'r') as f:
                deletion_result = json.load(f)
                # Add relevant info to our verification result
                if 'record_type' in deletion_result:
                    verification_result['record_type'] = deletion_result['record_type']
                if 'record_name' in deletion_result:
                    verification_result['record_name'] = deletion_result['record_name']
        except Exception as e:
            print(f"Warning: Could not read deletion result file: {e}")
    
    # Write the verification result to a file
    with open(OUTPUT_VERIFICATION_FILE, 'w') as f:
        json.dump(verification_result, f, indent=2)
    
    print("\n--- Verification Summary ---")
    
    if deletion_verified:
        print("✅ The DNS record was successfully deleted from Cloudflare.")
        sys.exit(0)
    else:
        print("❌ The DNS record deletion could not be verified or the record still exists.")
        sys.exit(1) 