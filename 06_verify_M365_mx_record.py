#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that MX records for Microsoft 365 were correctly added using the Cloudflare API.
Takes the domain as a command line argument.

Ensure your virtual environment is active before running this script.

Usage: 
  ./06_verify_mx_record.py yourdomain.com
"""

import os
import sys
import re
import json
import dns.resolver
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

def load_env():
    """Load environment variables from .env file."""
    load_dotenv()
    
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

def get_expected_mx_format():
    """
    Fetch the current MX record format from Microsoft's documentation.
    
    Returns:
        str: The MX record format string or a default if unable to fetch.
    """
    url = "https://learn.microsoft.com/en-us/microsoft-365/enterprise/external-domain-name-system-records?view=o365-worldwide"
    
    try:
        print("Fetching expected MX format from Microsoft documentation...")
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

def get_mx_records_from_google_dns(domain):
    """
    Query Google DNS (8.8.8.8) for MX records for the given domain.
    
    Args:
        domain (str): The domain to query.
        
    Returns:
        list: List of (priority, server) tuples for the MX records.
    """
    try:
        print(f"\n📡 Querying Google DNS (8.8.8.8) for MX records for {domain}...")
        
        # Create a resolver that uses Google DNS servers
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS servers
        
        answers = resolver.resolve(domain, 'MX')
        mx_records = []
        
        for rdata in answers:
            priority = rdata.preference
            server = str(rdata.exchange).rstrip('.')
            mx_records.append((priority, server))
            print(f"  Found MX record: Priority {priority}, Server: {server}")
        
        return mx_records
    
    except dns.resolver.NoAnswer:
        print(f"No MX records found for {domain} via Google DNS")
        return []
    except dns.resolver.NXDOMAIN:
        print(f"Domain {domain} does not exist in Google DNS")
        return []
    except Exception as e:
        print(f"Error querying MX records via Google DNS: {e}")
        return []

def get_mx_records_from_cloudflare(domain, zone_id, api_token):
    """
    Query Cloudflare API for MX records for the given domain.
    
    Args:
        domain (str): The domain to query.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        
    Returns:
        list: List of (priority, server) tuples for the MX records.
    """
    try:
        print(f"\n☁️ Querying Cloudflare API for MX records for {domain}...")
        
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=MX"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(endpoint, headers=headers)
        data = response.json()
        
        if not data.get('success'):
            error_msg = data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"Cloudflare API error: {error_msg}")
            return []
        
        mx_records = []
        for record in data.get('result', []):
            # Check if the record is for the domain we're looking for
            # The name could be the root domain or "@" for the root
            record_name = record.get('name', '')
            if record_name == domain or (record_name == '@' and record.get('zone_name') == domain):
                priority = record.get('priority', 0)
                server = record.get('content', '')
                mx_records.append((priority, server))
                print(f"  Found MX record in Cloudflare: Priority {priority}, Server: {server}")
        
        return mx_records
    
    except Exception as e:
        print(f"Error querying Cloudflare API: {e}")
        return []

def verify_microsoft_365_mx(domain):
    """
    Verify that the domain has the correct MX record for Microsoft 365.
    First checks Cloudflare, then Google DNS.
    
    Args:
        domain (str): The domain to verify.
        
    Returns:
        dict: Results of verification with both Cloudflare and Google DNS.
    """
    expected_format = get_expected_mx_format()
    expected_server = expected_format.format(domain=domain.replace('.', '-'))
    
    print(f"Expected Microsoft 365 MX record: {expected_server}")
    results = {
        "cloudflare": False,
        "google_dns": False
    }
    
    # Check Cloudflare first
    env = load_env()
    if env and 'api_token' in env and 'zone_id' in env:
        mx_records = get_mx_records_from_cloudflare(domain, env['zone_id'], env['api_token'])
        
        if not mx_records:
            print("❌ No MX records found in Cloudflare")
        else:
            # Check if any of the MX records match the expected format
            for priority, server in mx_records:
                if server.lower() == expected_server.lower():
                    print(f"✅ Found matching Microsoft 365 MX record with priority {priority} in Cloudflare")
                    print(f"MX record is correctly configured in Cloudflare")
                    results["cloudflare"] = True
                    break
            
            if not results["cloudflare"]:
                print("❌ No matching Microsoft 365 MX record found in Cloudflare")
    else:
        print("❌ Cloudflare API check skipped due to missing environment variables")
    
    # Always check Google DNS afterward
    mx_records = get_mx_records_from_google_dns(domain)
    
    if not mx_records:
        print("❌ No MX records found via Google DNS")
    else:
        # Check if any of the MX records match the expected format
        for priority, server in mx_records:
            if server.lower() == expected_server.lower():
                print(f"✅ Found matching Microsoft 365 MX record with priority {priority} via Google DNS")
                print(f"MX record is correctly configured in Google DNS")
                results["google_dns"] = True
                break
        
        if not results["google_dns"]:
            print("❌ No matching Microsoft 365 MX record found in Google DNS")
    
    return results

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yourdomain.com>")
        sys.exit(1)

    domain = sys.argv[1]
    
    print(f"--- Verifying MX Records for {domain} ---")
    results = verify_microsoft_365_mx(domain)
    
    print("\n--- Verification Summary ---")
    
    if results["cloudflare"]:
        print("✅ Cloudflare: MX record correctly configured")
    else:
        print("❌ Cloudflare: MX record missing or incorrect")
    
    if results["google_dns"]:
        print("✅ Google DNS: MX record correctly configured and propagated")
    else:
        print("❌ Google DNS: MX record missing, incorrect, or not yet propagated")
    
    if results["cloudflare"] and results["google_dns"]:
        print("\n--- Verification Successful ✅ ---")
        print("The Microsoft 365 MX record is correctly configured in both Cloudflare and Google DNS.")
        print("Mail for this domain should be delivered to Microsoft 365.")
        sys.exit(0)
    elif results["cloudflare"]:
        print("\n--- Verification Partially Successful ⚠️ ---")
        print("The MX record is correctly configured in Cloudflare but not yet visible in Google DNS.")
        print("DNS propagation may not be complete (can take up to 48 hours).")
        sys.exit(0)  # Still exit with success since Cloudflare is correctly configured
    else:
        print("\n--- Verification Failed ❌ ---")
        print("The Microsoft 365 MX record is NOT correctly configured.")
        print("Possible reasons:")
        print("  1. The record was not added correctly")
        print("  2. The domain may not be configured in Microsoft 365")
        sys.exit(1) 