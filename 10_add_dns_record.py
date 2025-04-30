#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to add a DNS record to Cloudflare using the Cloudflare API.
Takes the domain as a command line argument.
Reads the DNS record details from 09.output.record_details.json.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./10_add_dns_record.py yourdomain.com
  ./10_add_dns_record.py yourdomain.com --debug
"""

import os
import sys
import requests
import json
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "10"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
INPUT_RECORD_DETAILS_FILE = "09.output.record_details.json"
OUTPUT_RECORD_ID_FILE = f"{OUTPUT_PREFIX}record_id.txt"

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

def read_record_from_file(file_path):
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
            
        # Basic validation
        required_fields = ["type", "name", "content", "ttl"]
        missing_fields = [field for field in required_fields if field not in record_data]
        
        if missing_fields:
            print(f"Error: Missing required fields in record data: {', '.join(missing_fields)}")
            sys.exit(1)
            
        return record_data
    except FileNotFoundError:
        print(f"Error: Input file not found at {file_path}")
        print("This file should be created by the 09_process_M365_dns_records.py script.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading or parsing input file: {e}")
        sys.exit(1)

def add_dns_record(domain, zone_id, api_token, record_data, debug_mode=False):
    """
    Add a DNS record using the Cloudflare API.
    
    Args:
        domain (str): The domain name.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        record_data (dict): Dictionary with record details.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        dict: The JSON response from the Cloudflare API.
    """
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Special handling for SRV records
    if record_data.get("type") == "SRV":
        print("SRV record detected - using Cloudflare's specific SRV format")
        
        # For SRV records, the content field is used differently
        # We need to extract target, weight, port, and priority separately
        
        # Use defaults if not provided
        priority = record_data.get("priority", 1)
        weight = record_data.get("weight", 1)
        port = record_data.get("port", 443)
        target = record_data.get("content", "")  # The target domain
        
        # Cloudflare API expects SRV records in a special format
        payload = {
            "type": "SRV",
            "name": record_data["name"],
            "ttl": record_data["ttl"],
            "data": {
                "service": "_sip" if "_sip." in record_data["name"] else "_sipfederationtls",
                "proto": "_tls" if "_tls." in record_data["name"] else "_tcp",
                "name": domain,
                "priority": priority,
                "weight": weight,
                "port": port,
                "target": target
            }
        }
        
        print(f"SRV record details:")
        print(f"  Service: {payload['data']['service']}")
        print(f"  Protocol: {payload['data']['proto']}")
        print(f"  Name: {record_data['name']}")
        print(f"  Target: {target}")
        print(f"  Priority: {priority}")
        print(f"  Weight: {weight}")
        print(f"  Port: {port}")
    else:
        # Handle non-SRV records as before
        payload = {
            "type": record_data["type"],
            "name": record_data["name"],
            "content": record_data["content"],
            "ttl": record_data["ttl"]
        }
        
        # Add priority for MX records if provided
        if record_data.get("type") == "MX" and "priority" in record_data:
            payload["priority"] = record_data["priority"]
        
        print(f"Adding {payload['type']} record for {domain}:")
        print(f"  Name: {payload['name']}")
        print(f"  Content: {payload['content']}")
        print(f"  TTL: {payload['ttl']}")
        if "priority" in payload:
            print(f"  Priority: {payload['priority']}")
    
    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        # Hide token in debug output
        print(f"Headers: {{'Authorization': 'Bearer DEBUG_TOKEN', 'Content-Type': 'application/json'}}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        return {"success": True, "debug": True, "message": "Debug mode - no API call made"}
    
    print("\nPayload for API request:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
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
        
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yourdomain.com> [--debug]")
        sys.exit(1)

    domain = sys.argv[1]
    env = load_env(debug_mode)
    
    print(f"--- Adding DNS Record for {domain} ---")
    
    # Check if the input file exists
    if not os.path.exists(INPUT_RECORD_DETAILS_FILE):
        print(f"❌ Error: Input file not found at {INPUT_RECORD_DETAILS_FILE}")
        print("This file should be created by the 09_process_M365_dns_records.py script.")
        sys.exit(1)
    
    # Read record from file
    record_data = read_record_from_file(INPUT_RECORD_DETAILS_FILE)
    
    try:
        response = add_dns_record(domain, env["zone_id"], env["api_token"], record_data, debug_mode)
        
        print("\nAPI Response:")
        print(json.dumps(response, indent=2))
        
        if response.get("success"):
            print(f"\n✅ Successfully added {record_data['type']} record for {domain}")
            print("\nNOTE: DNS changes may take some time to propagate.")
            
            # Save record ID for verification
            if "result" in response and "id" in response["result"]:
                record_id = response["result"]["id"]
                with open(OUTPUT_RECORD_ID_FILE, "w") as f:
                    f.write(record_id)
                print(f"Record ID {record_id} saved for verification.")
            
            sys.exit(0)
        else:
            error_msg = response.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"\n❌ API Error: {error_msg}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1) 