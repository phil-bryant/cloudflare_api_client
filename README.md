# Cloudflare API Client

# #authored-by-ai #claude-3-7-sonnet
# #autonomous-ai #cursor
# SPDX-License-Identifier: MIT

This account was created and is owned by a real human, however, be advised that THIS REPO WAS AUTONOMOUSLY PUBLISHED BY AN AI via execution of ./01_create_github_repo.sh --personal --public

## Overview

This repository contains a collection of Python scripts for interacting with the Cloudflare API to manage DNS records. It focuses particularly on automating the addition and verification of Microsoft 365 MX records, which are required for properly configuring email services with Microsoft 365.

## Key Features

- Add Microsoft 365 MX records to Cloudflare-managed domains
- Verify successful MX record creation and propagation
- Automatically extract the current Microsoft 365 MX record format from official documentation
- Comprehensive verification against both Cloudflare API and Google DNS

## Scripts

### Setup and Requirements

- `01_create_github_repo.sh` - Creates and initializes the GitHub repository
- `02_create_venv.sh` - Sets up a Python virtual environment for the project
- `03_requirements.txt` - Lists Python package dependencies
- `04_load_requirements.sh` - Installs the required dependencies

### DNS Management Scripts

- `05_add_M365_mx_record.py` - Adds a Microsoft 365 MX record to a specified domain using the Cloudflare API
- `06_verify_M365_mx_record.py` - Verifies that the MX record was successfully added and has propagated to public DNS

## Usage

### Environment Setup

1. Clone this repository
2. Run `./02_create_venv.sh` to create the Python virtual environment
3. Run `./04_load_requirements.sh` to install dependencies
4. Create a `.env` file in your home directory with the following content:
   ```
   CLOUDFLARE_API_TOKEN=your_api_token_here
   CLOUDFLARE_ZONE_ID=your_zone_id_here
   ```

### Adding an MX Record for Microsoft 365

```bash
./05_add_M365_mx_record.py yourdomain.com
```

This will:
1. Fetch the current MX record format from Microsoft's documentation
2. Create the correct MX record for your domain in Cloudflare
3. Return a success message with the API response

### Verifying MX Record Creation and Propagation

```bash
./06_verify_M365_mx_record.py yourdomain.com
```

This will:
1. Check the Cloudflare API to verify the record was created correctly
2. Check Google DNS (8.8.8.8) to verify the record has propagated to public DNS
3. Provide a detailed verification summary

## Features

- **Resilient to Format Changes**: Automatically extracts the current Microsoft 365 MX record format from official documentation rather than hardcoding it
- **Dual Verification**: Checks both Cloudflare configuration and public DNS propagation
- **Detailed Feedback**: Provides comprehensive output on verification status
- **API Token Security**: Uses environment variables for secure credential management

## Requirements

- Python 3.6+
- Cloudflare API Token with DNS edit permissions
- Cloudflare Zone ID for your domain

