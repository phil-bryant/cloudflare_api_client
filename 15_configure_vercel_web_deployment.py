#!/usr/bin/env python3

# #authored-by-ai #gemini-2.5-pro #cursor
# SPDX-License-Identifier: MIT

"""
Script to configure a domain's DNS records on Cloudflare for a Vercel website deployment.
Specifically, this script adds the required A record for the root (apex) domain.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./15_configure_vercel_web_deployment.py yourdomain.com
  ./15_configure_vercel_web_deployment.py yourdomain.com --debug
"""

import os
import sys
import requests
import json
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "15"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
OUTPUT_RECORD_ID_FILE = f"{OUTPUT_PREFIX}record_id.txt"
OUTPUT_VERIFICATION_FILE = f"{OUTPUT_PREFIX}verification_results.json"

# Vercel's recommended IP for A records
VERCEL_A_RECORD_IP = "76.76.21.21"

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
        print("Debug mode enabled. Using dummy credentials.")
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

def add_vercel_a_record(domain, zone_id, api_token, debug_mode=False):
    """
    Add the Vercel A record to Cloudflare.
    
    Args:
        domain (str): The apex domain name (e.g., yourdomain.com).
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        dict: The JSON response from the Cloudflare API or a debug message.
    """
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Payload for the A record pointing to Vercel's IP
    payload = {
        "type": "A",
        "name": domain,  # For apex domain, name is the domain itself
        "content": VERCEL_A_RECORD_IP,
        "ttl": 60,  # Recommended TTL, can be adjusted
        "proxied": False # Vercel recommends DNS only for the A record
    }
    
    print(f"Configuring A record for Vercel deployment on {domain}:")
    print(f"  Name: {payload['name']}")
    print(f"  Type: {payload['type']}")
    print(f"  Content: {payload['content']}")
    print(f"  TTL: {payload['ttl']}")
    print(f"  Proxied: {payload['proxied']}")
    
    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        # Hide token in debug output
        print(f"Headers: {{'Authorization': 'Bearer DEBUG_TOKEN', 'Content-Type': 'application/json'}}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        # Return a mock success response for debug mode
        return {
            "success": True,
            "result": {"id": "DEBUG_RECORD_ID"},
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
        # Attempt to get error details from response body if available
        error_details = "No details available."
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                # Check for specific conflict error (record already exists)
                if e.response.status_code == 400 and any("record already exists" in err.get('message', '').lower() for err in error_data.get('errors', [])):
                    print("\n⚠️ Warning: A record likely already exists. Checking...")
                    # Attempt to find the existing record
                    existing_record = find_existing_a_record(domain, zone_id, api_token)
                    if existing_record:
                        print(f"✅ Found existing A record with ID: {existing_record['id']} pointing to {existing_record['content']}")
                        if existing_record['content'] == VERCEL_A_RECORD_IP:
                             print("Existing record already points to the correct Vercel IP.")
                             return {"success": True, "result": existing_record, "message": "Existing record already correct."}
                        else:
                             print(f"Existing record points to {existing_record['content']}. Consider updating or deleting it manually if needed.")
                             # You might want to offer to update it here in a future version
                             return {"success": False, "errors": [{"message": f"Existing A record found but points to {existing_record['content']}, not {VERCEL_A_RECORD_IP}"}]}
                    else:
                        print("Could not find the existing A record despite the conflict error.")
                        return {"success": False, "errors": [{"message": "Record already exists error, but could not retrieve existing record."}]}
                else:
                    error_details = error_data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            except json.JSONDecodeError:
                error_details = e.response.text
        return {"success": False, "errors": [{"message": f"API Request Failed: {error_details}"}]}
    except Exception as e:
        return {"success": False, "errors": [{"message": f"Unexpected error: {e}"}]}

def find_existing_a_record(domain, zone_id, api_token):
    """Find an existing A record for the apex domain."""
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    params = {
        "type": "A",
        "name": domain
    }
    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('success') and data.get('result'):
            # Should ideally only be one A record for the apex
            return data['result'][0]
    except Exception as e:
        print(f"Error searching for existing A record: {e}")
    return None

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
    # Basic validation: ensure it looks like a domain and not www.
    if domain.startswith("www."):
        print("Error: This script is intended for the root (apex) domain, not a 'www' subdomain.")
        print(f"Please provide the domain without 'www.', e.g., {domain.replace('www.', '')}")
        sys.exit(1)
    if '.' not in domain:
         print(f"Error: Invalid domain format provided: {domain}")
         sys.exit(1)

    env = load_env(debug_mode)
    
    print(f"--- Configuring Vercel A Record for {domain} ---")
    
    try:
        response = add_vercel_a_record(domain, env["zone_id"], env["api_token"], debug_mode)
        
        print("\nAPI Response:")
        print(json.dumps(response, indent=2))
        
        if response.get("success"):
            if response.get("message") == "Existing record already correct.":
                 print(f"\n✅ Vercel A record for {domain} already configured correctly.")
            else:
                print(f"\n✅ Successfully added Vercel A record for {domain}")
                print(f"   Record points to: {VERCEL_A_RECORD_IP}")
                print("\nNOTE: DNS changes may take some time to propagate.")
            
            # Save record ID for potential future verification/deletion scripts
            if "result" in response and "id" in response["result"]:
                record_id = response["result"]["id"]
                with open(OUTPUT_RECORD_ID_FILE, "w") as f:
                    f.write(record_id)
                print(f"Record ID {record_id} saved to {OUTPUT_RECORD_ID_FILE}")
            
            # Create a placeholder verification file indicating success
            verification_results = {
                "timestamp": os.path.getmtime(OUTPUT_RECORD_ID_FILE) if os.path.exists(OUTPUT_RECORD_ID_FILE) else None,
                "domain": domain,
                "record_type": "A",
                "record_name": domain,
                "expected_content": VERCEL_A_RECORD_IP,
                "cloudflare_configured": True,
                "action": "add"
            }
            with open(OUTPUT_VERIFICATION_FILE, 'w') as f:
                json.dump(verification_results, f, indent=2)
            print(f"Configuration result saved to {OUTPUT_VERIFICATION_FILE}")

            sys.exit(0)
        else:
            error_msg = response.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"\n❌ API Error: {error_msg}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Unexpected error during script execution: {e}")
        sys.exit(1) 