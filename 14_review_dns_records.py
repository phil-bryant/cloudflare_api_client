#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to review all DNS records from Cloudflare and provide options to
delete or verify each record.

Takes the domain as a command line argument.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./14_review_dns_records.py yourdomain.com
  ./14_review_dns_records.py yourdomain.com --debug
"""

import os
import sys
import json
import subprocess
import requests
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "14"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
TEMP_RECORD_ID_FILE = f"{SCRIPT_NUM}.output.record_id.txt"
OUTPUT_RECORD_DETAILS_FILE = f"{SCRIPT_NUM}.output.record_details.json"

# Define ANSI color codes
class Colors:
    RED = "\033[31m"
    ORANGE = "\033[38;5;208m"
    PURPLE = "\033[38;5;199m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BLUE = "\033[34m"
    RESET = "\033[0m"

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

def get_dns_records(zone_id, api_token, debug_mode=False):
    """
    Get all DNS records from Cloudflare.
    
    Args:
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        list: List of dictionaries, each containing a DNS record.
    """
    if debug_mode:
        print("DEBUG MODE: Using sample records instead of calling the Cloudflare API")
        return [
            {
                "id": "debug-record-1",
                "type": "A",
                "name": "example.com",
                "content": "192.0.2.1",
                "ttl": 3600,
                "proxied": False
            },
            {
                "id": "debug-record-2",
                "type": "CNAME",
                "name": "www.example.com",
                "content": "example.com",
                "ttl": 3600,
                "proxied": True
            }
        ]
    
    try:
        print(f"\nFetching DNS records from Cloudflare...")
        
        endpoint = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?per_page=100"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(endpoint, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            error_msg = data.get('errors', [{'message': 'Unknown error'}])[0]['message']
            print(f"Cloudflare API error: {error_msg}")
            return []
        
        records = data.get('result', [])
        print(f"Found {len(records)} DNS records in Cloudflare.")
        return records
    
    except Exception as e:
        print(f"Error fetching DNS records from Cloudflare: {e}")
        return []

def display_record(record, index, total):
    """
    Display the details of a DNS record.
    
    Args:
        record (dict): The DNS record to display.
        index (int): The current record index.
        total (int): The total number of records.
    """
    record_type = record.get('type', 'Unknown')
    record_name = record.get('name', 'Unknown')
    
    print(f"\n{Colors.CYAN}Record {index+1} of {total}{Colors.RESET}")
    print(f"{Colors.CYAN}{'='*50}{Colors.RESET}")
    
    print(f"{Colors.GREEN}ID:{Colors.RESET} {record.get('id', 'Unknown')}")
    print(f"{Colors.GREEN}Type:{Colors.RESET} {record_type}")
    print(f"{Colors.GREEN}Name:{Colors.RESET} {record_name}")
    print(f"{Colors.GREEN}Content:{Colors.RESET} {record.get('content', 'Unknown')}")
    print(f"{Colors.GREEN}TTL:{Colors.RESET} {record.get('ttl', 'Unknown')}")
    
    if record.get('proxied') is not None:
        proxied_status = "Yes" if record.get('proxied') else "No"
        print(f"{Colors.GREEN}Proxied:{Colors.RESET} {proxied_status}")
    
    # Display specialized fields based on record type
    if record_type == 'MX':
        print(f"{Colors.GREEN}Priority:{Colors.RESET} {record.get('priority', 'Unknown')}")
    
    elif record_type == 'SRV':
        data = record.get('data', {})
        if data:
            print(f"{Colors.GREEN}Service:{Colors.RESET} {data.get('service', 'Unknown')}")
            print(f"{Colors.GREEN}Protocol:{Colors.RESET} {data.get('proto', 'Unknown')}")
            print(f"{Colors.GREEN}Name:{Colors.RESET} {data.get('name', 'Unknown')}")
            print(f"{Colors.GREEN}Priority:{Colors.RESET} {data.get('priority', 'Unknown')}")
            print(f"{Colors.GREEN}Weight:{Colors.RESET} {data.get('weight', 'Unknown')}")
            print(f"{Colors.GREEN}Port:{Colors.RESET} {data.get('port', 'Unknown')}")
            print(f"{Colors.GREEN}Target:{Colors.RESET} {data.get('target', 'Unknown')}")
    
    if record.get('comment'):
        print(f"{Colors.GREEN}Comment:{Colors.RESET} {record.get('comment')}")
    
    if record.get('tags'):
        print(f"{Colors.GREEN}Tags:{Colors.RESET} {', '.join(record.get('tags'))}")

def run_script(script_name, domain, source_script_num=None, debug_mode=False):
    """
    Run another script from the current directory.
    
    Args:
        script_name (str): The name of the script to run.
        domain (str): The domain to pass to the script.
        source_script_num (str): The script number to look for input files from.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        bool: True if the script executed successfully, False otherwise.
    """
    try:
        cmd = [f"./{script_name}", domain]
        if source_script_num:
            cmd.append(source_script_num)
        if debug_mode:
            cmd.append("--debug")
            
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error running {script_name}: {e}")
        return False

def review_dns_records(domain, zone_id, api_token, debug_mode=False):
    """
    Review DNS records from Cloudflare and provide options for each record.
    
    Args:
        domain (str): The domain name.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        debug_mode (bool): Whether to run in debug mode.
    """
    # Get records from Cloudflare
    records = get_dns_records(zone_id, api_token, debug_mode)
    
    if not records:
        print("No records found to review. Exiting.")
        return
    
    # Process each record
    index = 0
    total = len(records)
    
    while index < total:
        record = records[index]
        display_record(record, index, total)
        
        # Prompt for action
        action = None
        while action not in ['N', 'D', 'V', 'Q']:
            action = input(f"\n{Colors.YELLOW}Choose an action:{Colors.RESET}\n"
                          f"[{Colors.GREEN}N{Colors.RESET}]ext record\n"
                          f"[{Colors.RED}D{Colors.RESET}]elete record\n"
                          f"[{Colors.BLUE}V{Colors.RESET}]erify record\n"
                          f"[{Colors.ORANGE}Q{Colors.RESET}]uit review\n"
                          f"Enter choice [N/D/V/Q]: ").strip().upper() or 'N'
        
        if action == 'Q':
            print(f"{Colors.ORANGE}Quitting record review.{Colors.RESET}")
            break
        
        elif action == 'D':
            print(f"{Colors.RED}Deleting record...{Colors.RESET}")
            
            # Save record ID for deletion
            with open(TEMP_RECORD_ID_FILE, "w") as f:
                f.write(record['id'])
            
            # Run delete and verification scripts
            if run_script("12_delete_dns_record.py", domain, SCRIPT_NUM, debug_mode):
                run_script("13_verify_delete_dns_record.py", domain, SCRIPT_NUM, debug_mode)
                print(f"{Colors.GREEN}Record deletion process completed.{Colors.RESET}")
                
                # Get updated records after deletion
                records = get_dns_records(zone_id, api_token, debug_mode)
                total = len(records)
                # Keep the same index to show the next record
                if index >= total:
                    index = total - 1 if total > 0 else 0
            else:
                print(f"{Colors.RED}Failed to delete record.{Colors.RESET}")
                # Move to next record
                index += 1
        
        elif action == 'V':
            print(f"{Colors.BLUE}Verifying record...{Colors.RESET}")
            
            # Save record ID for verification
            with open(TEMP_RECORD_ID_FILE, "w") as f:
                f.write(record['id'])
                
            # Save record details for verification
            record_details = {
                "type": record.get('type'),
                "name": record.get('name'),
                "content": record.get('content'),
                "ttl": record.get('ttl'),
                "proxied": record.get('proxied', False)
            }
            
            # Add special fields based on record type
            if record.get('type') == 'MX' and 'priority' in record:
                record_details['priority'] = record.get('priority')
            
            # Add SRV specific fields
            elif record.get('type') == 'SRV' and 'data' in record:
                data = record.get('data', {})
                if 'priority' in data:
                    record_details['priority'] = data.get('priority')
                if 'weight' in data:
                    record_details['weight'] = data.get('weight')
                if 'port' in data:
                    record_details['port'] = data.get('port')
                if 'target' in data:
                    record_details['content'] = data.get('target')
            
            # Save to JSON file
            with open(OUTPUT_RECORD_DETAILS_FILE, 'w') as f:
                json.dump(record_details, f, indent=2)
                
            # Run verification script with current script number
            if run_script("11_verify_add_dns_record.py", domain, SCRIPT_NUM, debug_mode):
                print(f"{Colors.GREEN}Record verification completed.{Colors.RESET}")
            else:
                print(f"{Colors.RED}Record verification failed.{Colors.RESET}")
            
            # Move to next record
            index += 1
        
        else:  # Next record
            # Move to next record
            index += 1
    
    print(f"\n{Colors.GREEN}--- DNS Record Review Complete ---{Colors.RESET}")
    print(f"Reviewed {total} records for {domain}")

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
    
    print(f"--- Reviewing DNS Records for {domain} ---")
    
    # Check if the necessary scripts exist
    required_scripts = [
        "11_verify_add_dns_record.py",
        "12_delete_dns_record.py",
        "13_verify_delete_dns_record.py"
    ]
    
    missing_scripts = [script for script in required_scripts if not os.path.exists(script)]
    
    if missing_scripts:
        print(f"❌ Error: Missing required scripts: {', '.join(missing_scripts)}")
        print("Please create these scripts before running this one.")
        sys.exit(1)
    
    try:
        review_dns_records(domain, env["zone_id"], env["api_token"], debug_mode)
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1) 