#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to add an MX record for Microsoft 365 using the Cloudflare API.
Takes the domain as a command line argument to keep domain names out of public repositories.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage: 
  ./06_add_mx_record.py yourdomain.com
  ./06_add_mx_record.py yourdomain.com --debug
"""

import os
import sys
import requests
import json
import re
from dotenv import load_dotenv
from bs4 import BeautifulSoup

def load_env(debug_mode=False):
    """Load environment variables from .env file."""
    load_dotenv()
    
    if debug_mode:
        return {
            "api_token": "DEBUG_TOKEN",
            "zone_id": "DEBUG_ZONE_ID"
        }
    
    required_vars = ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please add them to your .env file:")
        print("CLOUDFLARE_API_TOKEN=your_api_token_here")
        print("CLOUDFLARE_ZONE_ID=your_zone_id_here")
        sys.exit(1)
    
    return {
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN"),
        "zone_id": os.getenv("CLOUDFLARE_ZONE_ID")
    }

def get_mx_record_format():
    """
    Fetch the current MX record format from Microsoft's documentation.
    
    Returns:
        str: The MX record format string or a default if unable to fetch.
    """
    url = "https://learn.microsoft.com/en-us/microsoft-365/enterprise/external-domain-name-system-records?view=o365-worldwide"
    
    try:
        print(f"Fetching MX record format from Microsoft documentation: {url}")
        response = requests.get(url)
        print(f"Response status code: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the Exchange Online MX record section in the table
            for table in soup.find_all('table'):
                for row in table.find_all('tr'):
                    cells = row.find_all('td')
                    if len(cells) >= 2 and "MX" in cells[0].get_text():
                        value_text = cells[2].get_text()
                        print(f"Found MX record text: {value_text}")
                        # Look for the MX token format
                        match = re.search(r'<MX token>\.mail\.protection\.outlook\.com', value_text)
                        if match:
                            print("Found standard Microsoft 365 MX record format")
                            return "{domain}.mail.protection.outlook.com"
        
        # If we're here, we couldn't find the format in the docs
        print("Warning: Could not extract MX record format from Microsoft documentation.")
        print("Using default format: {domain}.mail.protection.outlook.com")
        return "{domain}.mail.protection.outlook.com"
    
    except Exception as e:
        print(f"Warning: Error fetching Microsoft documentation: {e}")
        print("Using default format: {domain}.mail.protection.outlook.com")
        return "{domain}.mail.protection.outlook.com"

def add_mx_record(domain, zone_id, api_token, debug_mode=False):
    """
    Add an MX record for Microsoft 365 using the Cloudflare API.
    
    Args:
        domain (str): The domain name (e.g., 'yourdomain.com').
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        debug_mode (bool): Whether to run in debug mode (no API calls)
        
    Returns:
        dict: The JSON response from the Cloudflare API.
    """
    # Get the current MX record format from Microsoft's documentation
    mx_format = get_mx_record_format()
    
    # Convert domain to the format required by Microsoft 365
    mx_content = mx_format.format(domain=domain.replace('.', '-'))
    
    endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "type": "MX",
        "name": "@",  # @ represents the root domain
        "content": mx_content,
        "ttl": 3600,  # 1 hour
        "priority": 0
    }
    
    print(f"Adding MX record for {domain} pointing to {mx_content}...")
    
    if debug_mode:
        print("\nDEBUG MODE: Would have made the following API call:")
        print(f"Endpoint: {endpoint}")
        print(f"Headers: {headers}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        return {"success": True, "debug": True, "message": "Debug mode - no API call made"}
    
    response = requests.post(endpoint, headers=headers, json=payload)
    
    try:
        return response.json()
    except json.JSONDecodeError:
        return {"success": False, "errors": [{"message": "Invalid JSON response"}]}

if __name__ == "__main__":
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        sys.argv.remove("--debug")
        
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yourdomain.com> [--debug]")
        sys.exit(1)

    domain = sys.argv[1]
    env = load_env(debug_mode)
    
    print(f"--- Adding MX Record for {domain} ---")
    
    try:
        response = add_mx_record(domain, env["zone_id"], env["api_token"], debug_mode)
        
        print("\nAPI Response:")
        print(json.dumps(response, indent=2))
        
        if response.get("success"):
            print(f"\nSuccessfully added MX record for {domain}")
            print("\nNOTE: DNS changes may take up to 48 hours to propagate worldwide.")
            print("      In practice, most places will see the change within a few hours.")
        else:
            print(f"\nAPI Error: {response.get('errors', [{'message': 'Unknown error'}])[0]['message']}")
            
    except requests.exceptions.RequestException as e:
        print(f"\nAPI Call Error: {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        
    print(f"--- Finished MX Record Addition for {domain} ---") 