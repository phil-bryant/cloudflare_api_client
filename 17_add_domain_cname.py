#!/usr/bin/env python3

# #authored-by-ai #gemini-2.5-pro #cursor
# SPDX-License-Identifier: MIT

"""
Script to add a CNAME record to a domain on Cloudflare.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID (Note: This script gets zone_id based on zone_domain argument)

Usage:
  ./17_add_domain_cname.py <zone_domain> <cname_name> <cname_target>
  ./17_add_domain_cname.py example.com api target.example.com
  ./17_add_domain_cname.py example.com www target.example.com --debug
"""

import os
import sys
import requests
import json
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "17"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
OUTPUT_RECORD_ID_FILE = f"{OUTPUT_PREFIX}record_id.txt"
OUTPUT_DETAILS_FILE = f"{OUTPUT_PREFIX}record_details.json"

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

def load_env(debug_mode=False):
    """Load environment variables from .env file."""
    dotenv_path = os.path.join(os.path.expanduser("~"), ".env")
    load_dotenv(dotenv_path=dotenv_path)

    if debug_mode:
        print("Debug mode enabled. Using dummy credentials.")
        # In debug mode, we still need a token for potential zone lookup
        # but won't make the actual add request.
        return {
            "api_token": os.getenv("CLOUDFLARE_API_TOKEN", "DEBUG_TOKEN")
        }

    required_vars = ["CLOUDFLARE_API_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Error: Missing required environment variable: {', '.join(missing_vars)}")
        print(f"Please add it to your {dotenv_path} file:")
        print("CLOUDFLARE_API_TOKEN=your_api_token_here")
        sys.exit(1)

    return {
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN")
    }

def get_zone_id(api_token, zone_domain):
    """Get the Zone ID for a given domain name."""
    print(f"Fetching Zone ID for domain: {zone_domain}")
    endpoint = "https://api.cloudflare.com/client/v4/zones"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    params = {"name": zone_domain}
    
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("success") and data["result"]:
            zone_id = data["result"][0]["id"]
            print(f"Found Zone ID: {zone_id}")
            return zone_id
        else:
            error_msg = data.get("errors", [{"message": f"Zone not found or API error for {zone_domain}"}])[0]["message"]
            print(f"❌ Error finding Zone ID: {error_msg}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ API Request Error getting Zone ID: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error getting Zone ID: {e}")
        return None

def add_cname_record(zone_id, api_token, cname_name, cname_target, zone_domain, debug_mode=False):
    """
    Add a CNAME record to Cloudflare.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        cname_name (str): The name of the CNAME record (e.g., 'www', 'api').
        cname_target (str): The target hostname the CNAME points to.
        zone_domain (str): The base domain name for constructing the full CNAME.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        dict: The JSON response from the Cloudflare API or a debug message.
    """
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Construct the full name (e.g., api.example.com)
    full_cname = f"{cname_name}.{zone_domain}"

    payload = {
        "type": "CNAME",
        "name": full_cname,
        "content": cname_target,
        "ttl": 60,  # Default TTL, can be adjusted
        "proxied": False # Default to DNS only, can be changed if needed
    }
    
    print(f"Adding CNAME record:")
    print(f"  Name: {payload['name']}")
    print(f"  Type: {payload['type']}")
    print(f"  Target (Content): {payload['content']}")
    print(f"  TTL: {payload['ttl']}")
    print(f"  Proxied: {payload['proxied']}")
    
    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        print(f"Headers: {{'Authorization': 'Bearer DEBUG_TOKEN', 'Content-Type': 'application/json'}}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        return {
            "success": True,
            "result": {"id": "DEBUG_RECORD_ID", **payload}, # Include payload in debug result
            "debug": True,
            "message": "Debug mode - no API call made"
        }
    
    print("\nPayload for API request:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        error_details = "No details available."
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                if e.response.status_code == 400 and any("record already exists" in err.get('message', '').lower() for err in error_data.get('errors', [])):
                     error_details = f"Record already exists for {full_cname}"
                     # Optionally, find and return existing record info here
                else:
                    error_details = error_data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            except json.JSONDecodeError:
                error_details = e.response.text
        return {"success": False, "errors": [{"message": f"API Request Failed: {error_details}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": f"Unexpected error: {e}"}]}

if __name__ == "__main__":
    cleanup_old_output_files()
    
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")
        
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <zone_domain> <cname_name> <cname_target> [--debug]")
        print("Example: ./17_add_domain_cname.py example.com api target.example.com")
        sys.exit(1)

    zone_domain = sys.argv[1]
    cname_name = sys.argv[2]
    cname_target = sys.argv[3]

    # Basic validation
    if '.' not in zone_domain:
         print(f"Error: Invalid zone domain format: {zone_domain}")
         sys.exit(1)
    if cname_name == '@' or '.' in cname_name:
         print(f"Error: Invalid CNAME name format: {cname_name} (Should be like 'www', 'api', etc.)")
         sys.exit(1)
    if '.' not in cname_target:
         print(f"Error: Invalid CNAME target format: {cname_target}")
         sys.exit(1)

    env = load_env(debug_mode)
    
    print(f"--- Adding CNAME Record {cname_name}.{zone_domain} -> {cname_target} ---")

    # Get Zone ID unless in debug mode (where we don't strictly need it)
    zone_id = None
    if not debug_mode:
        zone_id = get_zone_id(env["api_token"], zone_domain)
        if not zone_id:
            sys.exit(1)
    else:
        # Use a placeholder for debug mode prints
        zone_id = "DEBUG_ZONE_ID"
        print(f"Debug mode: Skipping Zone ID lookup for {zone_domain}")

    try:
        response = add_cname_record(zone_id, env["api_token"], cname_name, cname_target, zone_domain, debug_mode)
        
        print("\nAPI Response:")
        print(json.dumps(response, indent=2))
        
        if response.get("success"):
            record_details = response.get("result", {})
            record_id = record_details.get("id", "DEBUG_RECORD_ID" if debug_mode else None)
            
            print(f"\n✅ Successfully added CNAME record {cname_name}.{zone_domain}")
            print(f"   Record points to: {cname_target}")
            print("\nNOTE: DNS changes may take some time to propagate.")
            
            if record_id:
                with open(OUTPUT_RECORD_ID_FILE, "w") as f:
                    f.write(record_id)
                print(f"Record ID {record_id} saved to {OUTPUT_RECORD_ID_FILE}")
                
                # Save record details
                output_details = {
                    "timestamp": os.path.getmtime(OUTPUT_RECORD_ID_FILE) if os.path.exists(OUTPUT_RECORD_ID_FILE) else None,
                    "zone_domain": zone_domain,
                    "record_id": record_id,
                    "record_type": "CNAME",
                    "record_name": record_details.get("name"),
                    "record_content": record_details.get("content"),
                    "record_ttl": record_details.get("ttl"),
                    "record_proxied": record_details.get("proxied"),
                    "action": "add"
                }
                with open(OUTPUT_DETAILS_FILE, 'w') as f:
                    json.dump(output_details, f, indent=2)
                print(f"Record details saved to {OUTPUT_DETAILS_FILE}")
            
            sys.exit(0)
        else:
            error_msg = response.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"\n❌ API Error: {error_msg}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error during script execution: {e}")
        sys.exit(1) 