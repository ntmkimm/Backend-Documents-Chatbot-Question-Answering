import requests
import json
import sys
from typing import Dict, List, Optional
from pathlib import Path
import time 

# Configuration
API_BASE = "http://localhost:4427/api"
AUTH_TOKEN = "1234567890"
NOTEBOOK_NAME = "yuu"
NOTEBOOK_DESCRIPTION = "empty"
ID_FILE = "id_notebook"

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
    print_colored("Getting existing notebooks...", Colors.YELLOW)
    
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
    print_colored("Deleting existing notebooks...", Colors.YELLOW)
    
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

import uuid
def create_notebook() -> str:
    """Create new notebook and return its ID"""
    print_colored("Creating new notebook...", Colors.YELLOW)
    
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
    print_colored("Saving notebook ID to file...", Colors.YELLOW)
    
    try:
        with open(ID_FILE, 'w') as f:
            f.write(notebook_id)
        
        print_colored(f"Notebook ID saved to file: {ID_FILE}", Colors.GREEN)
        print(f"Content: {notebook_id}")
        print()
        
    except Exception as e:
        print_colored(f"Failed to save notebook ID to file: {e}", Colors.RED)
        sys.exit(1)

def get_existing_sources(notebook_id: str) -> List[Dict]:
    """Get list of existing sources"""
    print_colored("Getting existing sources...", Colors.YELLOW)
    
    try:
        sources = make_request('GET', '/sources')
        
        print("Current sources:")
        print(json.dumps(sources, indent=2))
        print()
        
        return sources
    except Exception as e:
        print_colored(f"Failed to get sources (this might be normal if no sources exist): {e}", Colors.YELLOW)
        return []

def delete_existing_sources(sources: List[Dict], notebook_id: str):
    """Delete existing sources for the notebook"""
    print_colored("Deleting existing sources...", Colors.YELLOW)
    
    # Find sources to delete for this notebook
    sources_to_delete = []
    
    for source in sources:
        sources_to_delete.append(source.get('id'))
    
    # Delete sources
    if sources_to_delete:
        for source_id in sources_to_delete:
            if source_id:
                print(f"Deleting existing source: {source_id}")
                try:
                    make_request('DELETE', f'/sources/{source_id}')
                    print(f"Deleted source: {source_id}")
                except Exception as e:
                    print_colored(f"Failed to delete source {source_id}: {e}", Colors.RED)
    else:
        print("No existing sources found to delete")
    
    print()
    
def main():
    DATA = Path(
        "/mlcv2/WorkingSpace/Personal/quannh/Project/Project/TRNS-AI/ntmkim/Work/DocsQA/data/test-data"
    )
    QA_JSON_FILE = Path(
        "/mlcv2/WorkingSpace/Personal/quannh/Project/Project/TRNS-AI/ntmkim/Work/DocsQA/data/qa_with_new.json"
    )
    with open(QA_JSON_FILE, "r") as fi:
        qa_data = json.load(fi)
        
    existing_notebooks = get_existing_notebooks()
    delete_existing_notebooks(existing_notebooks)
    notebook_id = create_notebook()
    save_notebook_id(notebook_id=notebook_id)
    sources = get_existing_sources(notebook_id=notebook_id)
    delete_existing_sources(sources=sources, notebook_id=notebook_id)
    
    _qas = []
    batch_size = 1
    file_paths = []
    for ext in ["*.doc", "*.pdf"]:
        file_paths.extend(DATA.glob(ext))
        
    for i in range(0, len(file_paths), batch_size):
        print(f"\n\n\n\nProcessing new {batch_size} files")
        
        # update đủ batch size data
        for file_path in file_paths[i:i+batch_size]:
            print("ADDING FILE: ", file_path.name)
            payload = {
                "notebook_id": notebook_id,
                "source_id": str(uuid.uuid4()),
                "type": 'upload',
                "file_path": str(file_path),
                "content": None,
                "title": None,
                "transformations": [],
                "embed": True,
                "delete_source": False,
            }   
            
            make_request('POST', '/sources', payload)
            
            for _qa in qa_data:
                if _qa['doc'] == file_path.name: 
                    _qa['note'] = "Câu hỏi của document."
    
        # ask chat trong document
        payload = {
            "chat_message": "hello",
            "notebook_id": notebook_id,
            "session_id": "",
            "source_ids": [],
        }
        
        response = make_request('POST', '/notebooks/ask_chat', payload)
        session_id = response["session_id"]
        
        count_in_source = 0
        count_out_source = 0
        for _id, _qa in enumerate(qa_data):
            
            note = _qa.get("note", "")
            if not note:
                count_out_source += 1
                if count_out_source > 30:
                    continue
            else:
                count_in_source += 1
                if count_out_source > 30:
                    continue
            
            payload = {
                "chat_message": _qa['question'],
                "notebook_id": notebook_id,
                "session_id": session_id,
                "source_ids": [],
            }
            response = make_request('POST', '/notebooks/ask_chat', payload)
            response['question'] = _qa['question']
            response['gt'] = _qa['answer']
            response['difficulty'] = _qa['difficulty']
            response["note"] = _qa.get("note", "Câu hỏi không nằm trong document.")
        
            print(json.dumps(response, ensure_ascii=False, indent=4).encode('utf8').decode())
    
        # xóa hết document trong đây
        sources = get_existing_sources(notebook_id=notebook_id)
        delete_existing_sources(sources=sources, notebook_id=notebook_id)
        break
        
        
if __name__ == "__main__":
    main()
    
    

