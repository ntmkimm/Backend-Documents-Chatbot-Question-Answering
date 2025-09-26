import requests, json
import uuid

API_BASE = "http://localhost:4427/api"
headers = {"Content-Type": "application/json", "accept": "application/json"}
from typing import List, Union, AsyncGenerator, Dict, Optional
API_BASE = "http://localhost:4427/api"
AUTH_TOKEN = "1234567890"
ID_NOTEBOOK_FILE = "utils/id_notebook"
EXAMPLE_SOURCE_FILE = "utils/example_source.txt"

# Colors for console output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
import os
import sys
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
            response = requests.get(url, headers=headers)
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

def load_notebook_id() -> str:
    """Load notebook ID from file"""
    print_colored("Loading notebook ID from file...", Colors.BLUE)
    
    try:
        if not os.path.exists(ID_NOTEBOOK_FILE):
            print_colored(f"Notebook ID file not found: {ID_NOTEBOOK_FILE}", Colors.RED)
            print_colored("Please run auto_setup_step2_notebooks.py first", Colors.RED)
            sys.exit(1)
        
        with open(ID_NOTEBOOK_FILE, 'r') as f:
            notebook_id = f.read().strip()
        
        if not notebook_id:
            print_colored("Notebook ID file is empty", Colors.RED)
            sys.exit(1)
        
        print_colored(f"Loaded notebook ID: {notebook_id}", Colors.GREEN)
        return notebook_id
        
    except Exception as e:
        print_colored(f"Failed to load notebook ID: {e}", Colors.RED)
        sys.exit(1)

payload = {
  "chat_message": "where is thailand?",
  "notebook_id": load_notebook_id(),
  "session_id": str(uuid.uuid4()),
}

events = []
with requests.post(API_BASE + "/notebooks/ask_chat",
                   headers=headers, json=payload, stream=True) as r:
    # r.raise_for_status()
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        print(line)

