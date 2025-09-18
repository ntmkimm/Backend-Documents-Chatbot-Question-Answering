#!/usr/bin/env python3
"""
Script to setup notebooks via API:
1. Get existing notebooks
2. Delete old notebooks with same name
3. Create new notebook
4. Save notebook ID to file
"""

import requests
import json
import sys
from typing import Dict, List, Optional
import uuid

# Configuration
API_BASE = "http://localhost:4427/api"
AUTH_TOKEN = "1234567890"
NOTEBOOK_NAME = "yuu"
NOTEBOOK_DESCRIPTION = "empty"
ID_FILE = "utils/id_notebook"

# Colors for console output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def print_colored(message: str, color: str = Colors.NC):
    """Print colored message to console"""
    print(f"{color}{message}{Colors.NC}")

def make_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
    """Make HTTP request to API"""
    url = f"{API_BASE}{endpoint}"
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {AUTH_TOKEN}'
    }
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers, json=data if data else None)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, headers=headers)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        print_colored(f"Request failed: {e}", Colors.RED)
        if hasattr(e.response, 'text'):
            print_colored(f"Response: {e.response.text}", Colors.RED)
        sys.exit(1)

def get_existing_notebooks() -> List[Dict]:
    """Get list of existing notebooks"""
    print_colored("Step 1: Getting existing notebooks...", Colors.YELLOW)
    
    # Note: The GET request also includes data payload as per your example
    data = {
        "name": NOTEBOOK_NAME,
        "description": NOTEBOOK_DESCRIPTION
    }
    
    notebooks = make_request('GET', '/notebooks', data)
    
    print("Current notebooks:")
    print(json.dumps(notebooks, indent=2))
    print()
    
    return notebooks

def delete_existing_notebooks(notebooks: List[Dict]):
    """Delete existing notebooks with same name"""
    print_colored("Step 2: Deleting existing notebooks...", Colors.YELLOW)
    
    # Find notebooks to delete
    notebooks_to_delete = []
    
    for notebook in notebooks:
        if notebook.get('name') == NOTEBOOK_NAME:
            notebooks_to_delete.append(notebook.get('id'))
    
    # Delete notebooks
    for notebook_id in notebooks_to_delete:
        if notebook_id:
            print(f"Deleting existing notebook: {notebook_id}")
            try:
                # Note: DELETE request doesn't need data payload for notebooks
                make_request('DELETE', f'/notebooks/{notebook_id}')
                print(f"Deleted notebook: {notebook_id}")
            except Exception as e:
                print_colored(f"Failed to delete notebook {notebook_id}: {e}", Colors.RED)
        else:
            print("No existing notebooks found to delete")
    
    print()

def create_notebook() -> str:
    """Create new notebook and return its ID"""
    print_colored("Step 3: Creating new notebook...", Colors.YELLOW)
    
    data = {
        "notebook_id": str(uuid.uuid4()),
        "name": NOTEBOOK_NAME,
        "description": NOTEBOOK_DESCRIPTION
    }
    
    response = make_request('POST', '/notebooks', data)
    print("Notebook creation response:")
    print(json.dumps(response, indent=2))
    
    notebook_id = response.get('id')
    if not notebook_id:
        print_colored("Failed to create notebook", Colors.RED)
        sys.exit(1)
    
    print_colored(f"Created notebook with ID: {notebook_id}", Colors.GREEN)
    print()
    
    return notebook_id

def save_notebook_id(notebook_id: str):
    """Save notebook ID to file"""
    print_colored("Step 4: Saving notebook ID to file...", Colors.YELLOW)
    
    try:
        with open(ID_FILE, 'w') as f:
            f.write(notebook_id)
        
        print_colored(f"Notebook ID saved to file: {ID_FILE}", Colors.GREEN)
        print(f"Content: {notebook_id}")
        print()
        
    except Exception as e:
        print_colored(f"Failed to save notebook ID to file: {e}", Colors.RED)
        sys.exit(1)

def verify_final_setup():
    """Verify final setup by getting notebooks list"""
    print_colored("Step 5: Verifying final setup...", Colors.YELLOW)
    
    data = {
        "name": NOTEBOOK_NAME,
        "description": NOTEBOOK_DESCRIPTION
    }
    
    notebooks = make_request('GET', '/notebooks', data)
    print("Final notebooks list:")
    print(json.dumps(notebooks, indent=2))

def main():
    """Main function to orchestrate the notebook setup process"""
    print_colored("Starting notebook setup process...\n", Colors.BLUE)
    
    try:
        # Step 1: Get existing notebooks
        existing_notebooks = get_existing_notebooks()
        
        # Step 2: Delete existing notebooks with same name
        delete_existing_notebooks(existing_notebooks)
        
        # Step 3: Create new notebook
        notebook_id = create_notebook()
        
        # Step 4: Save notebook ID to file
        save_notebook_id(notebook_id)
        
        # Step 5: Verify final setup
        verify_final_setup()
        
        print_colored("\nNotebook setup completed successfully!", Colors.GREEN)
        print_colored(f"Notebook ID: {notebook_id}", Colors.GREEN)
        print_colored(f"ID saved to file: {ID_FILE}", Colors.GREEN)
        
    except KeyboardInterrupt:
        print_colored("\nProcess interrupted by user", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        print_colored(f"Unexpected error: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()