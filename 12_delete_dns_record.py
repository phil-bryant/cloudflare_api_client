#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to delete a DNS record from Cloudflare using the Cloudflare API.
Takes the domain as a command line argument.
Reads the record ID from 09.output.record_id.txt.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./12_delete_dns_record.py yourdomain.com
  ./12_delete_dns_record.py yourdomain.com <source_script_num>
  ./12_delete_dns_record.py yourdomain.com --debug
"""

import os
import sys
import requests
import json
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "12"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_ID_FILE = "09.output.record_id.txt"
OUTPUT_DELETION_FILE = f"{OUTPUT_PREFIX}deletion_result.json"

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

def load_env(debug_mode=False):
    """Load environment variables from .env file."""
    # Look for .env in the home directory
    dotenv_path = os.path.join(os.path.expanduser("~"), ".env")
    load_dotenv(dotenv_path=dotenv_path)

    if debug_mode:
        return {
            "api_token": "DEBUG_TOKEN",
            "zone_id": "DEBUG_ZONE_ID"
        }

    required_vars = ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print(f"Please add them to your {dotenv_path} file:")
        print("CLOUDFLARE_API_TOKEN=your_api_token_here")
        print("CLOUDFLARE_ZONE_ID=your_zone_id_here")
        sys.exit(1)

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
        str: The record ID.
    """
    try:
        print(f"Reading record ID from: {file_path}")
        with open(file_path, 'r') as f:
            record_id = f.read().strip()
            
        if not record_id:
            print("Error: Empty record ID in file.")
            sys.exit(1)
            
        return record_id
    except FileNotFoundError:
        print(f"Error: Record ID file not found at {file_path}")
        print("This file should be created by the 09_process_M365_dns_records.py script.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading record ID file: {e}")
        sys.exit(1)

def get_record_details(zone_id, api_token, record_id, debug_mode=False):
    """
    Get the details of a DNS record from Cloudflare.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to get.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        dict: The record details or None if not found.
    """
    if debug_mode:
        return {
            "type": "DEBUG_TYPE",
            "name": "DEBUG_NAME",
            "content": "DEBUG_CONTENT"
        }
        
    try:
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 404:
            print(f"Record with ID {record_id} not found in Cloudflare")
            return None
            
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            error_msg = data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"Cloudflare API error: {error_msg}")
            return None
        
        return data.get('result', {})
    except Exception as e:
        print(f"Error getting record details: {e}")
        return None

def delete_dns_record(domain, zone_id, api_token, record_id, debug_mode=False):
    """
    Delete a DNS record using the Cloudflare API.
    
    Args:
        domain (str): The domain name (for context).
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_id (str): The ID of the record to delete.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        dict: The JSON response from the Cloudflare API.
    """
    # Get record details for logging before deletion
    record_details = get_record_details(zone_id, api_token, record_id, debug_mode)
    
    if record_details:
        print(f"Found record to delete:")
        print(f"  Type: {record_details.get('type')}")
        print(f"  Name: {record_details.get('name')}")
        print(f"  Content: {record_details.get('content')}")
    else:
        print("Warning: Could not fetch details of record to delete. Proceeding with deletion anyway.")
    
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    print(f"Deleting DNS record with ID {record_id} for {domain}...")
    
    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        print(f"Method: DELETE")
        # Hide token in debug output
        print(f"Headers: {{'Authorization': 'Bearer DEBUG_TOKEN', 'Content-Type': 'application/json'}}")
        return {"success": True, "debug": True, "message": "Debug mode - no API call made"}
    
    try:
        response = requests.delete(endpoint, headers=headers)
        
        if response.status_code == 404:
            return {"success": False, "errors": [{"message": f"Record with ID {record_id} not found"}]}
            
        response.raise_for_status()
        result = response.json()
        
        # Save deletion result to file
        deletion_result = {
            "record_id": record_id,
            "domain": domain,
            "record_type": record_details.get('type') if record_details else "unknown",
            "record_name": record_details.get('name') if record_details else "unknown",
            "success": result.get('success', False)
        }
        
        with open(OUTPUT_DELETION_FILE, 'w') as f:
            json.dump(deletion_result, f, indent=2)
            
        return result
    except requests.exceptions.RequestException as e:
        # Attempt to get error details from response body if available
        error_details = "No details available."
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_details = error_data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            except json.JSONDecodeError:
                error_details = e.response.text
        return {"success": False, "errors": [{"message": f"API Request Failed: {error_details}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": f"Unexpected error: {e}"}]}

if __name__ == "__main__":
    # Clean up old output files at startup
    cleanup_old_output_files()
    
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")
    
    # Check for valid number of arguments
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: {sys.argv[0]} <yourdomain.com> [source_script_num] [--debug]")
        sys.exit(1)

    domain = sys.argv[1]
    
    # Check if there's a source script number provided
    if len(sys.argv) == 3:
        source_script_num = sys.argv[2]
        # Check if it's a debug flag
        if source_script_num != "--debug":
            INPUT_RECORD_ID_FILE = f"{source_script_num}.output.record_id.txt"
            print(f"Using input file from script {source_script_num}")
    
    env = load_env(debug_mode)
    
    print(f"--- Deleting DNS Record for {domain} ---")
    
    # Check if the input file exists
    if not os.path.exists(INPUT_RECORD_ID_FILE):
        print(f"❌ Error: Record ID file not found at {INPUT_RECORD_ID_FILE}")
        print("This file should be created by the 09_process_M365_dns_records.py script.")
        sys.exit(1)
    
    # Read record ID from file
    record_id = read_record_id_from_file(INPUT_RECORD_ID_FILE)
    
    try:
        response = delete_dns_record(domain, env["zone_id"], env["api_token"], record_id, debug_mode)
        
        print("\nAPI Response:")
        print(json.dumps(response, indent=2))
        
        if response.get("success"):
            print(f"\n✅ Successfully deleted DNS record with ID {record_id} for {domain}")
            sys.exit(0)
        else:
            error_msg = response.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"\n❌ API Error: {error_msg}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1) 