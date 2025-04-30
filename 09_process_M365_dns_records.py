#!/usr/bin/env python3

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

"""
Script to process Microsoft 365 DNS records from PowerShell output.
Compares each record to what exists in Cloudflare and provides options to add/update.

Takes the domain as a command line argument.
Reads the DNS records from temp_output.txt.

Ensure your virtual environment is active and ~/.env file is populated with:
- CLOUDFLARE_API_TOKEN
- CLOUDFLARE_ZONE_ID

Usage:
  ./09_process_M365_dns_records.py yourdomain.com
  ./09_process_M365_dns_records.py yourdomain.com --debug
"""

import os
import sys
import json
import re
import subprocess
import requests
import glob
import shutil
from dotenv import load_dotenv

# Define file naming conventions
SCRIPT_NUM = "09"
OUTPUT_PREFIX = f"{SCRIPT_NUM}.output."
TEMP_RECORD_DETAILS_FILE = f"{OUTPUT_PREFIX}record_details.json"
TEMP_RECORD_ID_FILE = f"{OUTPUT_PREFIX}record_id.txt"
CLEANED_INPUT_FILE = f"{OUTPUT_PREFIX}cleaned_input.txt"

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

# Define the path to the input file relative to this script's location
INPUT_FILE_PATH = os.path.join(os.path.dirname(__file__), "..", "ms_graph_ps", "05.output.powershell.output.txt")

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

def parse_dns_records_from_file(file_path):
    """
    Parse DNS records from the PowerShell output file.
    
    Args:
        file_path (str): Path to the PowerShell output file.
        
    Returns:
        list: List of dictionaries, each containing a DNS record.
    """
    try:
        print(f"Reading DNS records from: {file_path}")
        with open(file_path, 'r') as f:
            content = f.read()
            
        records = []
        
        # Find the JSON array in the file
        # The JSON data starts with '[' and ends with ']'
        json_start = content.find('[')
        json_end = content.rfind(']') + 1
        
        if json_start == -1 or json_end == 0:
            print("Warning: No JSON data found in the file.")
            return []
            
        json_content = content[json_start:json_end]
        
        try:
            # Parse the JSON data
            ms_records = json.loads(json_content)
            
            for i, ms_record in enumerate(ms_records, 1):
                record_type = ms_record.get('RecordType', '')
                label = ms_record.get('Label', '')
                ttl = ms_record.get('Ttl', 3600)
                add_props = ms_record.get('AdditionalProperties', {})
                
                # Skip unsupported record types
                if record_type not in ['Mx', 'Txt', 'CName', 'Srv']:
                    print(f"Skipping unsupported record type: {record_type}")
                    continue
                
                # Convert Microsoft Graph record type to Cloudflare record type
                cf_record_type = {
                    'Mx': 'MX',
                    'Txt': 'TXT',
                    'CName': 'CNAME',
                    'Srv': 'SRV'
                }.get(record_type, record_type)
                
                # Initialize the record with common fields
                record = {
                    "id": i,
                    "type": cf_record_type,
                    "name": label,
                    "ttl": ttl
                }
                
                # Add type-specific fields
                if record_type == 'Mx':
                    record["content"] = add_props.get('mailExchange', '')
                    record["priority"] = add_props.get('preference', 0)
                
                elif record_type == 'Txt':
                    record["content"] = add_props.get('text', '')
                
                elif record_type == 'CName':
                    record["content"] = add_props.get('canonicalName', '')
                
                elif record_type == 'Srv':
                    record["content"] = add_props.get('nameTarget', '')
                    record["priority"] = add_props.get('priority', 0)
                    record["weight"] = add_props.get('weight', 1)
                    record["port"] = add_props.get('port', 443)
                
                records.append(record)
                print(f"Found record {i}: {cf_record_type} - {label}")
            
            if not records:
                print("Warning: No DNS records found in the JSON data.")
                
            return records
            
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON data: {e}")
            print("Falling back to regex pattern matching...")
            
            # If JSON parsing fails, fall back to the original regex pattern matching
            pattern = r"RecordType\s*:\s*(\w+)\s*Name\s*:\s*([^\n]+)\s*Value\s*:\s*([^\n]+)(?:\s*Priority\s*:\s*(\d+))?\s*TTL\s*:\s*(\d+)"
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for i, match in enumerate(matches, 1):
                record_type = match.group(1).strip()
                name = match.group(2).strip()
                value = match.group(3).strip()
                priority = match.group(4).strip() if match.group(4) else None
                ttl = int(match.group(5).strip())
                
                record = {
                    "id": i,
                    "type": record_type,
                    "name": name,
                    "content": value,
                    "ttl": ttl
                }
                
                if priority:
                    record["priority"] = int(priority)
                
                # For SRV records, add default values for weight and port
                if record_type == "SRV":
                    # Default weight to 1 for SRV records
                    record["weight"] = 1
                    
                    # Try to determine the port based on the service
                    if "_sip._tls" in name:
                        record["port"] = 443
                    elif "_sipfederationtls._tcp" in name:
                        record["port"] = 5061
                    else:
                        # Default to 443 if we can't determine
                        record["port"] = 443
                    
                records.append(record)
                print(f"Found record {i}: {record_type} - {name}")
            
            if not records:
                print("Warning: No DNS records found with regex pattern matching either.")
                
            return records
    
    except FileNotFoundError:
        print(f"Error: Input file not found at {file_path}")
        print("Please ensure the ms_graph_ps project exists at the expected location and has generated the output file.")
        sys.exit(1)
    except Exception as e:
        print(f"Error parsing DNS records from file: {e}")
        sys.exit(1)

def get_existing_dns_records(domain, zone_id, api_token):
    """
    Get existing DNS records from Cloudflare.
    
    Args:
        domain (str): The domain name.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        
    Returns:
        list: List of dictionaries, each containing a DNS record.
    """
    try:
        print(f"\nFetching existing DNS records from Cloudflare for {domain}...")
        
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

def records_match(record1, record2):
    """
    Check if two DNS records match.
    
    Args:
        record1, record2 (dict): The DNS records to compare.
        
    Returns:
        bool: True if the records match, False otherwise.
    """
    # Basic fields to compare
    fields = ["type", "name", "content"]
    
    # TTL is not critical for matching
    for field in fields:
        if field in record1 and field in record2:
            # Some normalization for comparison
            if record1[field].lower() != record2[field].lower():
                return False
        else:
            # If field doesn't exist in both records, they don't match
            return False
    
    # Special handling for MX and SRV records that need priority
    if record1.get("type") in ["MX", "SRV"]:
        if "priority" in record1 and "priority" in record2:
            if record1["priority"] != record2["priority"]:
                return False
        else:
            # If priority is missing in either record for MX/SRV, they don't match
            return False
    
    return True

def get_record_differences(record1, record2):
    """
    Get detailed differences between two DNS records.
    
    Args:
        record1, record2 (dict): The DNS records to compare.
        
    Returns:
        dict: Dictionary of field names and their differences.
    """
    differences = {}
    
    # Compare basic fields
    for field in ["type", "name", "content", "ttl"]:
        if field in record1 and field in record2:
            value1 = record1[field]
            value2 = record2[field]
            
            # Convert to string for comparison if not already
            if not isinstance(value1, str):
                value1 = str(value1)
            if not isinstance(value2, str):
                value2 = str(value2)
                
            # Case-insensitive comparison for type, name, and content
            if field in ["type", "name", "content"]:
                if value1.lower() != value2.lower():
                    differences[field] = {
                        "existing": value1,
                        "proposed": value2
                    }
            else:
                # Direct comparison for other fields like TTL
                if value1 != value2:
                    differences[field] = {
                        "existing": value1,
                        "proposed": value2
                    }
    
    # Compare priority for MX and SRV records
    if record1.get("type") in ["MX", "SRV"]:
        if "priority" in record1 and "priority" in record2:
            if record1["priority"] != record2["priority"]:
                differences["priority"] = {
                    "existing": str(record1["priority"]),
                    "proposed": str(record2["priority"])
                }
        elif "priority" in record1:
            differences["priority"] = {
                "existing": str(record1["priority"]),
                "proposed": "missing"
            }
        elif "priority" in record2:
            differences["priority"] = {
                "existing": "missing",
                "proposed": str(record2["priority"])
            }
    
    return differences

# Define ANSI color codes
class Colors:
    RED = "\033[31m"
    ORANGE = "\033[38;5;208m"
    PURPLE = "\033[38;5;199m"  # Changed from purple to bright hot pink
    GREEN = "\033[32m"
    RESET = "\033[0m"

def print_colored_comparison(field, existing_value, proposed_value):
    """
    Print colored comparison of field values.
    
    Args:
        field (str): Field name
        existing_value (str): Existing value
        proposed_value (str): Proposed value
    """
    values_match = existing_value.lower() == proposed_value.lower()
    
    if values_match:
        # When values match, print in green
        print(f"{Colors.GREEN}{field}{Colors.RESET} - Existing = {Colors.GREEN}{existing_value}{Colors.RESET}")
        print(f"{Colors.GREEN}{field}{Colors.RESET} - PROPOSED -> {Colors.GREEN}{proposed_value}{Colors.RESET}")
    else:
        # When values differ, use different colors
        print(f"{Colors.RED}{field}{Colors.RESET} - Existing = {Colors.ORANGE}{existing_value}{Colors.RESET}")
        print(f"{Colors.RED}{field}{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{proposed_value}{Colors.RESET}")
    print()  # Empty line after each attribute

def find_matching_record(record, existing_records):
    """
    Find a matching record in the list of existing records.
    
    Args:
        record (dict): The record to find.
        existing_records (list): List of existing records.
        
    Returns:
        dict: The matching record if found, None otherwise.
    """
    for existing in existing_records:
        if records_match(record, existing):
            return existing
    return None

def run_script(script_name, domain, debug_mode=False):
    """
    Run another script from the current directory.
    
    Args:
        script_name (str): The name of the script to run.
        domain (str): The domain to pass to the script.
        debug_mode (bool): Whether to run in debug mode.
        
    Returns:
        bool: True if the script executed successfully, False otherwise.
    """
    try:
        cmd = [f"./{script_name}", domain]
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

def process_dns_records(domain, zone_id, api_token, debug_mode=False):
    """
    Process DNS records from the PowerShell output file.
    
    Args:
        domain (str): The domain name.
        zone_id (str): The Cloudflare Zone ID.
        api_token (str): The Cloudflare API token.
        debug_mode (bool): Whether to run in debug mode.
    """
    # Parse records from the PowerShell output file
    records = parse_dns_records_from_file(INPUT_FILE_PATH)
    
    if not records:
        print("No records found to process. Exiting.")
        return
    
    # Get existing records from Cloudflare
    existing_records = get_existing_dns_records(domain, zone_id, api_token)
    
    # Process each record
    for record in records:
        print(f"\n--- Processing Record {record['id']}: {record['type']} - {record['name']} ---")
        
        # Check if the record already exists in Cloudflare
        matching_record = find_matching_record(record, existing_records)
        
        if matching_record:
            print("✅ Record already exists in Cloudflare with matching values.")
            continue
        
        # Find a record with the same type and name but different values
        similar_records = [r for r in existing_records if r['type'] == record['type'] and r['name'].lower() == record['name'].lower()]
        
        if similar_records:
            # Record exists but needs updating
            existing = similar_records[0]
            print("⚠️ Similar record exists but with different values:")
            
            # Get detailed differences
            differences = get_record_differences(existing, record)
            
            # Replace detailed attribute comparison header
            print("\nATTRIBUTE - Disposition => VALUE")
            
            # Always show Record Type and Record Name first
            print_colored_comparison("RECORD TYPE", existing['type'], record['type'])
            print_colored_comparison("RECORD NAME", existing['name'], record['name'])
            
            # Then show the other differences
            for field, values in differences.items():
                if field.lower() not in ['type', 'name']:  # Skip type and name since we've already shown them
                    print_colored_comparison(field.upper(), values["existing"], values["proposed"])
            
            # Prompt for update
            response = input("\nUpdate existing record? [Y/n]: ").strip().lower() or "y"
            
            if response == "y":
                # Create temporary file with record ID for deletion script
                with open(TEMP_RECORD_ID_FILE, "w") as f:
                    f.write(existing['id'])
                
                print(f"Deleting existing record with ID: {existing['id']}...")
                if not debug_mode:
                    # Run delete and verification scripts
                    if not run_script("12_delete_dns_record.py", domain, debug_mode):
                        print("❌ Failed to delete existing record. Skipping update.")
                        continue
                    
                    if not run_script("13_verify_delete_dns_record.py", domain, debug_mode):
                        print("⚠️ Could not verify record deletion.")
                
                # Create temporary file with record details for addition script
                with open(TEMP_RECORD_DETAILS_FILE, "w") as f:
                    json.dump(record, f)
                
                print(f"Adding new record...")
                if not debug_mode:
                    # Run add and verification scripts
                    if not run_script("10_add_dns_record.py", domain, debug_mode):
                        print("❌ Failed to add new record.")
                        continue
                    
                    if not run_script("11_verify_add_dns_record.py", domain, debug_mode):
                        print("⚠️ Could not verify record addition.")
                
                print("✅ Record updated successfully.")
            else:
                print("Skipping record update.")
        else:
            # New record
            print("🆕 Record does not exist in Cloudflare.")
            
            # Display record details
            print("\nATTRIBUTE - Disposition => VALUE")
            print(f"{Colors.GREEN}RECORD TYPE{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['type']}{Colors.RESET}")
            print()
            print(f"{Colors.GREEN}RECORD NAME{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['name']}{Colors.RESET}")
            print()
            print(f"{Colors.GREEN}CONTENT{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['content']}{Colors.RESET}")
            print()
            print(f"{Colors.GREEN}TTL{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['ttl']}{Colors.RESET}")
            print()
            
            # Display priority if applicable
            if 'priority' in record:
                print(f"{Colors.GREEN}PRIORITY{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['priority']}{Colors.RESET}")
                print()
            
            # Display weight and port for SRV records
            if record['type'] == 'SRV':
                if 'weight' in record:
                    print(f"{Colors.GREEN}WEIGHT{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['weight']}{Colors.RESET}")
                    print()
                
                if 'port' in record:
                    print(f"{Colors.GREEN}PORT{Colors.RESET} - PROPOSED -> {Colors.PURPLE}{record['port']}{Colors.RESET}")
                    print()
            
            # Prompt for addition
            response = input("Add this record? [Y/n]: ").strip().lower() or "y"
            
            if response == "y":
                # Ensure SRV records have all required fields
                if record['type'] == 'SRV':
                    # Make sure weight is included
                    if 'weight' not in record:
                        record['weight'] = 1
                    
                    # Make sure port is included
                    if 'port' not in record:
                        record['port'] = 443
                
                # Create temporary file with record details for addition script
                with open(TEMP_RECORD_DETAILS_FILE, "w") as f:
                    json.dump(record, f)
                    
                # For debugging - also save to a persistent file
                debug_filename = f"{OUTPUT_PREFIX}debug_{record['type']}_{record['name'].replace('.', '_')}.json"
                with open(debug_filename, "w") as f:
                    json.dump(record, f, indent=2)
                
                print(f"Adding new record...")
                if not debug_mode:
                    # Run add and verification scripts
                    if not run_script("10_add_dns_record.py", domain, debug_mode):
                        print("❌ Failed to add new record.")
                        continue
                    
                    if not run_script("11_verify_add_dns_record.py", domain, debug_mode):
                        print("⚠️ Could not verify record addition.")
                
                print("✅ Record added successfully.")
            else:
                print("Skipping record addition.")
    
    # Clean up temporary files - moved to use our file naming convention
    # Now controlled by the other scripts' cleanup routines
    
    print("\n--- DNS Record Processing Complete ---")
    print(f"Processed {len(records)} records from {INPUT_FILE_PATH}")

def clean_input_file(input_path, output_path):
    """
    Clean the input file by removing ANSI color codes and other non-JSON content.
    
    Args:
        input_path (str): Path to the input file.
        output_path (str): Path to save the cleaned output.
        
    Returns:
        bool: True if cleaning was successful, False otherwise.
    """
    try:
        with open(input_path, 'r') as f:
            content = f.read()
            
        # Remove ANSI color codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        content = ansi_escape.sub('', content)
        
        # Find the JSON array in the file
        json_start = content.find('[')
        json_end = content.rfind(']') + 1
        
        if json_start == -1 or json_end == 0:
            print("Warning: No JSON data found in the input file.")
            return False
        
        # Extract only the JSON content
        json_content = content[json_start:json_end]
        
        # Remove any VERBOSE lines that might be inside the JSON
        json_lines = [line for line in json_content.split('\n') if not line.strip().startswith('VERBOSE:')]
        json_content = '\n'.join(json_lines)
        
        # Save the cleaned content
        with open(output_path, 'w') as f:
            f.write(json_content)
            
        # Validate the JSON before returning
        try:
            json.loads(json_content)
            print(f"Cleaned and validated JSON saved to: {output_path}")
            return True
        except json.JSONDecodeError as e:
            print(f"Warning: Cleaned file contains invalid JSON: {e}")
            return False
    except Exception as e:
        print(f"Error cleaning input file: {e}")
        return False

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
    
    print(f"--- Processing Microsoft 365 DNS Records for {domain} ---")
    
    # Check if the necessary scripts exist
    required_scripts = [
        "10_add_dns_record.py",
        "11_verify_add_dns_record.py",
        "12_delete_dns_record.py",
        "13_verify_delete_dns_record.py"
    ]
    
    missing_scripts = [script for script in required_scripts if not os.path.exists(script)]
    
    if missing_scripts:
        print(f"❌ Error: Missing required scripts: {', '.join(missing_scripts)}")
        print("Please create these scripts before running this one.")
        sys.exit(1)
    
    # Check if the input file exists
    if not os.path.exists(INPUT_FILE_PATH):
        print(f"❌ Error: Input file not found at {INPUT_FILE_PATH}")
        print("Please ensure the ms_graph_ps project exists at the expected location and has generated the output file.")
        sys.exit(1)
    
    try:
        # Clean the input file before processing
        if clean_input_file(INPUT_FILE_PATH, CLEANED_INPUT_FILE):
            # Override the input file path to use the cleaned version
            original_input_path = INPUT_FILE_PATH
            INPUT_FILE_PATH = CLEANED_INPUT_FILE
            
            # Process the DNS records
            process_dns_records(domain, env["zone_id"], env["api_token"], debug_mode)
            
            # Restore the original input path
            INPUT_FILE_PATH = original_input_path
        else:
            print("❌ Failed to clean input file. Proceeding with original file.")
            process_dns_records(domain, env["zone_id"], env["api_token"], debug_mode)
    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1) 