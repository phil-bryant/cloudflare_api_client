#!/usr/bin/env python3

# #authored-by-ai #gemini-pro-1.5
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to verify that the TXT verification record for Microsoft 365 was correctly added.
Reads expected value from ../ms_graph_ps/03.output.powershell.output.txt.
Takes the domain as a command line argument.

Checks Cloudflare API and Google DNS.

Usage: 
  ./08_verify_M365_txt_verification_record.py yourdomain.com
"""

import os
import sys
import json
import dns.resolver
import requests
from dotenv import load_dotenv

# Define the path to the input file relative to this script's location
INPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "ms_graph_ps", "03.output.powershell.output.txt")

def load_env():
    """Load environment variables from .env file in home directory."""
    dotenv_path = os.path.join(os.path.expanduser("~"), ".env")
    load_dotenv(dotenv_path=dotenv_path)

    required_vars = ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ZONE_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print(f"Warning: Missing environment variables: {', '.join(missing_vars)} in {dotenv_path}")
        print("Cloudflare API verification will be skipped")
        return {}

    return {
        "api_token": os.getenv("CLOUDFLARE_API_TOKEN"),
        "zone_id": os.getenv("CLOUDFLARE_ZONE_ID")
    }

def read_expected_txt_value_from_file(file_path):
    """
    Read the expected TXT record value from the specified file.

    Args:
        file_path (str): Path to the input file.

    Returns:
        str: The expected TXT value, or None if not found/error.
    """
    try:
        print(f"Reading expected TXT value from: {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()

        start_index = content.rfind('{')
        end_index = content.rfind('}')

        if start_index != -1 and end_index != -1 and start_index < end_index:
            json_str = content[start_index : end_index + 1]
            try:
                record_data = json.loads(json_str)
                if 'value' in record_data and record_data.get('type', '').lower() == 'txt':
                    print(f"Successfully parsed expected TXT value: {record_data['value']}")
                    return record_data['value']
                else:
                    print("Error: Parsed JSON does not contain a valid TXT 'value' field.")
                    return None
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from file: {e}")
                return None
        else:
            print("Error: Could not find JSON block in the input file.")
            return None

    except FileNotFoundError:
        print(f"Error: Input file not found at {file_path}")
        return None
    except Exception as e:
        print(f"Error reading or parsing input file: {e}")
        return None

def get_txt_records_from_google_dns(domain):
    """
    Query Google DNS (8.8.8.8) for TXT records for the given domain.

    Args:
        domain (str): The domain to query.

    Returns:
        list: List of TXT record content strings.
    """
    try:
        print(f"\n📡 Querying Google DNS (8.8.8.8) for TXT records for {domain}...")
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['8.8.8.8', '8.8.4.4']

        answers = resolver.resolve(domain, 'TXT')
        txt_records = []

        for rdata in answers:
            # TXT records can be split into multiple strings, concatenate them
            record_text = b''.join(rdata.strings).decode('utf-8')
            txt_records.append(record_text)
            print(f"  Found TXT record: {record_text}")

        return txt_records

    except dns.resolver.NoAnswer:
        print(f"No TXT records found for {domain} via Google DNS")
        return []
    except dns.resolver.NXDOMAIN:
        print(f"Domain {domain} does not exist in Google DNS")
        return []
    except Exception as e:
        print(f"Error querying TXT records via Google DNS: {e}")
        return []

def get_txt_records_from_cloudflare(domain, zone_id, api_token):
    """
    Query Cloudflare API for TXT records for the given domain.

    Args:
        domain (str): The domain to query.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.

    Returns:
        list: List of TXT record content strings.
    """
    if not api_token or not zone_id:
        print("\n☁️ Cloudflare API check skipped due to missing credentials.")
        return None # Indicate skipped check

    try:
        print(f"\n☁️ Querying Cloudflare API for TXT records for {domain}...")
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=TXT&name={domain}"
        # Also check for root record if domain query yields nothing
        endpoint_root = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?type=TXT&name=@"

        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

        txt_records = []

        # Query for both domain name and root record name ("@")
        for ep in [endpoint, endpoint_root]:
             print(f"  Querying endpoint: {ep.split('?')[0]}?type=TXT&name={ep.split('name=')[-1]}") # Mask token in log
             response = requests.get(ep, headers=headers)
             data = response.json()

             if not data.get('success'):
                 error_msg = data.get('errors', [{'message': 'Unknown error'}])[0]['message']
                 print(f"  Cloudflare API error: {error_msg}")
                 # Don't stop, try the other endpoint if applicable
                 continue

             for record in data.get('result', []):
                 content = record.get('content', '')
                 if content and content not in txt_records: # Avoid duplicates if both @ and domain return same
                     txt_records.append(content)
                     print(f"  Found TXT record in Cloudflare (Name: {record.get('name')}, Content: {content})")

        return txt_records # Returns list, even if empty

    except Exception as e:
        print(f"Error querying Cloudflare API: {e}")
        return None # Indicate error/skipped check

def verify_microsoft_365_txt(domain):
    """
    Verify that the domain has the correct TXT record for Microsoft 365 verification.

    Args:
        domain (str): The domain to verify.

    Returns:
        dict: Results of verification with both Cloudflare and Google DNS.
    """
    expected_value = read_expected_txt_value_from_file(INPUT_FILE_PATH)
    if not expected_value:
        print("Cannot proceed without expected TXT value from input file.")
        return {"cloudflare": False, "google_dns": False, "error": True}

    print(f"Expected Microsoft 365 TXT record value: {expected_value}")
    results = {
        "cloudflare": False,
        "google_dns": False,
        "error": False
    }

    # Check Cloudflare
    env = load_env()
    cloudflare_records = get_txt_records_from_cloudflare(domain, env.get("zone_id"), env.get("api_token"))

    if cloudflare_records is None: # Indicates skipped or error
        print("❌ Cloudflare API check skipped or failed.")
        # We can't confirm via Cloudflare, but don't mark as definitively false yet
    elif not cloudflare_records:
        print("❌ No TXT records found in Cloudflare for this domain/name.")
    else:
        if expected_value in cloudflare_records:
            print(f"✅ Found matching Microsoft 365 TXT record in Cloudflare")
            results["cloudflare"] = True
        else:
            print("❌ Expected TXT record value NOT found in Cloudflare records.")
            print(f"   Expected: {expected_value}")
            print(f"   Found: {cloudflare_records}")

    # Check Google DNS
    google_dns_records = get_txt_records_from_google_dns(domain)

    if not google_dns_records:
        print("❌ No TXT records found via Google DNS")
    else:
        if expected_value in google_dns_records:
            print(f"✅ Found matching Microsoft 365 TXT record via Google DNS")
            results["google_dns"] = True
        else:
            print("❌ Expected TXT record value NOT found in Google DNS records.")
            print(f"   Expected: {expected_value}")
            print(f"   Found: {google_dns_records}")

    return results

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <yourdomain.com>")
        sys.exit(1)

    domain = sys.argv[1]

    print(f"--- Verifying M365 TXT Verification Record for {domain} ---")
    results = verify_microsoft_365_txt(domain)

    print("\n--- Verification Summary ---")

    if results.get("error"):
         print("❌ Verification could not be completed due to errors reading input file.")
         sys.exit(1)

    # Interpret Cloudflare results (handle skipped case)
    env_loaded = load_env()
    if not env_loaded or not env_loaded.get("api_token") or not env_loaded.get("zone_id"):
        print("⚪ Cloudflare: Check skipped (missing API credentials)")
    elif results["cloudflare"]:
        print("✅ Cloudflare: TXT record correctly configured")
    else:
        print("❌ Cloudflare: TXT record missing or incorrect")

    # Interpret Google DNS results
    if results["google_dns"]:
        print("✅ Google DNS: TXT record correctly configured and propagated")
    else:
        print("❌ Google DNS: TXT record missing, incorrect, or not yet propagated")

    # Determine overall success and exit code
    if results["google_dns"]:
        print("\n--- Verification Successful via Public DNS ✅ ---")
        print("The Microsoft 365 TXT verification record is correctly configured and visible in public DNS.")
        print("You should now be able to verify the domain in the Microsoft 365 admin center.")
        sys.exit(0)
    elif results["cloudflare"]:
        print("\n--- Verification Partially Successful ⚠️ ---")
        print("The TXT record is correctly configured in Cloudflare but not yet visible in Google DNS.")
        print("DNS propagation may take time. Wait a while and try verifying again.")
        print("You might still be able to verify in the M365 admin center if it checks Cloudflare directly or propagation is faster elsewhere.")
        sys.exit(0) # Exit success as Cloudflare is correct
    else:
        print("\n--- Verification Failed ❌ ---")
        print("The Microsoft 365 TXT verification record was NOT found or is incorrect in Cloudflare (if checked) and Google DNS.")
        print("Please ensure script 07 ran successfully and check your Cloudflare DNS settings.")
        sys.exit(1) 