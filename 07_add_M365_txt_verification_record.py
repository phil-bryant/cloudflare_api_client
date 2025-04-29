#!/usr/bin/env python3

# #authored-by-ai #gemini-pro-1.5
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to add a TXT verification record for Microsoft 365 using the Cloudflare API.
Takes the domain as a command line argument.
Reads the TXT record details from ../ms_graph_ps/03.output.powershell.output.txt.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./07_add_M365_txt_verification_record.py yourdomain.com
  ./07_add_M365_txt_verification_record.py yourdomain.com --debug
"""

import os
import sys
import requests
import json
from dotenv import load_dotenv

# Define the path to the input file relative to this script's location
INPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "ms_graph_ps", "03.output.powershell.output.txt")

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

def read_txt_record_from_file(file_path):
    """
    Read the TXT record details from the specified file.
    Assumes the file contains PowerShell output with a JSON block at the end.

    Args:
        file_path (str): Path to the input file.

    Returns:
        dict: Dictionary containing the TXT record details (type, name, value, ttl) or None if not found/error.
    """
    try:
        print(f"Reading TXT record details from: {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()

        # Find the JSON block (assuming it starts with '{' and ends with '}')
        start_index = content.rfind('{')
        end_index = content.rfind('}')

        if start_index != -1 and end_index != -1 and start_index < end_index:
            json_str = content[start_index : end_index + 1]
            try:
                record_data = json.loads(json_str)
                # Basic validation
                if all(k in record_data for k in ['type', 'name', 'value', 'ttl']) and record_data['type'].lower() == 'txt':
                    print("Successfully parsed TXT record data from file.")
                    return record_data
                else:
                    print("Error: Parsed JSON does not contain valid TXT record fields.")
                    return None
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from file: {e}")
                print(f"Extracted string: {json_str}")
                return None
        else:
            print("Error: Could not find JSON block in the input file.")
            return None

    except FileNotFoundError:
        print(f"Error: Input file not found at {file_path}")
        print("Please ensure the ms_graph_ps project exists at the expected location and has generated the output file.")
        return None
    except Exception as e:
        print(f"Error reading or parsing input file: {e}")
        return None


def add_txt_record(domain, zone_id, api_token, txt_record_data, debug_mode=False):
    """
    Add a TXT verification record using the Cloudflare API.

    Args:
        domain (str): The domain name (unused directly in payload, but good for context).
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        txt_record_data (dict): Dictionary with keys 'type', 'name', 'value', 'ttl'.
        debug_mode (bool): Whether to run in debug mode (no API calls).

    Returns:
        dict: The JSON response from the Cloudflare API or debug info.
    """
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    # Use details directly from the input file
    payload = {
        "type": txt_record_data['type'],
        "name": txt_record_data['name'],  # Typically '@' for root domain verification
        "content": txt_record_data['value'],
        "ttl": txt_record_data['ttl'],
    }

    print(f"Adding {payload['type']} record for {domain} with Name: {payload['name']}, Value: {payload['content']}, TTL: {payload['ttl']}...")

    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        # Avoid printing sensitive token in debug
        print(f"Headers: {{'Authorization': 'Bearer DEBUG_TOKEN', 'Content-Type': 'application/json'}}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        return {"success": True, "debug": True, "message": "Debug mode - no API call made"}

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Call Error: {e}")
        # Attempt to get error details from response body if available
        error_details = "No details available."
        if e.response is not None:
            try:
                error_data = e.response.json()
                error_details = error_data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            except json.JSONDecodeError:
                error_details = e.response.text
        return {"success": False, "errors": [{"message": f"API Request Failed: {error_details}"}]}
    except json.JSONDecodeError:
         # Handle cases where the response is not valid JSON (e.g., HTML error page)
        return {"success": False, "errors": [{"message": "Invalid JSON response received from API"}]}


if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yourdomain.com> [--debug]")
        print("  <yourdomain.com>: The domain being verified (used for context and potentially zone lookup in future).")
        sys.exit(1)

    domain = sys.argv[1]
    env = load_env(debug_mode)

    print(f"--- Adding M365 TXT Verification Record for {domain} ---")

    # Read TXT details from file
    txt_record_data = read_txt_record_from_file(INPUT_FILE_PATH)

    if not txt_record_data:
        print("\nExiting due to inability to read TXT record data.")
        sys.exit(1)

    try:
        response = add_txt_record(domain, env["zone_id"], env["api_token"], txt_record_data, debug_mode)

        print("\nAPI Response:")
        print(json.dumps(response, indent=2))

        if response.get("success"):
            print(f"\nSuccessfully added TXT verification record for {domain}")
            print("\nNOTE: DNS changes may take some time to propagate.")
            print("      You can use script 08_verify_M365_txt_verification_record.py to check propagation.")
            print("      You may also need to trigger verification within the Microsoft 365 admin center.")
            exit_code = 0
        else:
            error_msg = response.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"\nAPI Error: {error_msg}")
            # Check for common error: record already exists
            if "already exists" in error_msg:
                 print("Hint: The record might already exist in Cloudflare. Check your DNS settings.")
            exit_code = 1

    except Exception as e:
        print(f"\nUnexpected error during API call: {e}")
        exit_code = 1

    print(f"--- Finished TXT Record Addition for {domain} ---")
    sys.exit(exit_code) 