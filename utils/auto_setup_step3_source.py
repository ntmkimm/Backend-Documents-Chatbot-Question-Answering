#!/usr/bin/env python3
"""
Script to setup sources via API:
1. Get existing sources
2. Delete old sources
3. Create new text source with content from file
4. Get random transformation from API
"""
import uuid
import requests
import json
import sys
import random
import os
from typing import Dict, List, Optional

# Configuration
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

def load_source_content() -> str:
    """Load source content from file"""
    print_colored("Loading source content from file...", Colors.BLUE)
    
    try:
        if not os.path.exists(EXAMPLE_SOURCE_FILE):
            print_colored(f"Source content file not found: {EXAMPLE_SOURCE_FILE}", Colors.RED)
            print_colored("Creating example file with default content...", Colors.YELLOW)
            
            # Create example file with default content
            default_content = """Quân khu 2 của Thái Lan thông báo trên Facebook rằng các cuộc giao tranh hiện đã lan rộng ra 6 khu vực: Prasat Ta Muen Thom, Prasat Ta Kwai, Chong Bok, Khao Phra Wihan (Preah Vihear), Chong An Ma và Chong Chom. Thông báo cho biết một máy bay chiến đấu F-16 đã được triển khai và đã thực hiện không kích vào một vị trí quân sự của Campuchia. Tờ The Nation của Thái Lan đưa tin, F-16 của Thái Lan đã tấn công một căn cứ quân sự của Campuchia gần khu vực biên giới. "Chúng tôi đã sử dụng không lực để tấn công các mục tiêu quân sự theo đúng kế hoạch", đại tá Richa Suksuwanon, phó phát ngôn viên quân đội Thái Lan, nói với phóng viên Channel News Asia."""
            
            with open(EXAMPLE_SOURCE_FILE, 'w', encoding='utf-8') as f:
                f.write(default_content)
            
            print_colored(f"Created example file: {EXAMPLE_SOURCE_FILE}", Colors.GREEN)
        
        with open(EXAMPLE_SOURCE_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        if not content:
            print_colored("Source content file is empty", Colors.RED)
            sys.exit(1)
        
        print_colored(f"Loaded source content ({len(content)} characters)", Colors.GREEN)
        return content
        
    except Exception as e:
        print_colored(f"Failed to load source content: {e}", Colors.RED)
        sys.exit(1)

def get_transformations() -> List[Dict]:
    """Get list of available transformations"""
    print_colored("Step 1: Getting available transformations...", Colors.YELLOW)
    
    transformations = make_request('GET', '/transformations')
    
    print("Available transformations:")
    print(json.dumps(transformations, indent=2))
    print()
    
    return transformations

def get_random_transformation(transformations: List[Dict]) -> str:
    """Get random transformation ID"""
    if not transformations:
        print_colored("No transformations available", Colors.RED)
        sys.exit(1)
    
    random_transformation = random.choice(transformations)
    transformation_id = random_transformation.get('id')
    
    print_colored(f"Selected random transformation: {transformation_id}", Colors.GREEN)
    print(f"Transformation details: {json.dumps(random_transformation, indent=2)}")
    print()
    
    return transformation_id

def get_existing_sources(notebook_id: str) -> List[Dict]:
    """Get list of existing sources"""
    print_colored("Step 2: Getting existing sources...", Colors.YELLOW)
    
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
    print_colored("Step 3: Deleting existing sources...", Colors.YELLOW)
    
    # Find sources to delete for this notebook
    sources_to_delete = []
    
    for source in sources:
        # Check if source belongs to our notebook
        if source.get('notebook_id') == notebook_id:
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

def create_text_source(notebook_id: str, content: str, transformation_id: str) -> str:
    """Create new text source and return its ID"""
    print_colored("Step 4: Creating new text source...", Colors.YELLOW)
    
    data = {
        "notebook_id": notebook_id,
        "source_id": str(uuid.uuid4()),
        "type": "text",
        "content": content,
        "transformations": [transformation_id],
        "embed": True,
        "delete_source": False
    }
    
    response = make_request('POST', '/sources', data)
    print("Text source creation response:")
    print(json.dumps(response, indent=2))
    
    source_id = response.get('id')
    if not source_id:
        print_colored("Failed to create text source", Colors.RED)
        sys.exit(1)
    
    print_colored(f"Created text source with ID: {source_id}", Colors.GREEN)
    print()
    
    return source_id

def verify_final_setup(notebook_id: str):
    """Verify final setup by getting sources list"""
    print_colored("Step 5: Verifying final setup...", Colors.YELLOW)
    
    try:
        sources = make_request('GET', '/sources')
        
        # Filter sources for our notebook
        notebook_sources = [s for s in sources if s.get('notebook_id') == notebook_id]
        
        print("Final sources for our notebook:")
        print(json.dumps(notebook_sources, indent=2))
    except Exception as e:
        print_colored(f"Failed to verify setup: {e}", Colors.RED)

def main():
    """Main function to orchestrate the source setup process"""
    print_colored("Starting source setup process...\n", Colors.BLUE)
    
    try:
        # Load notebook ID and source content
        notebook_id = load_notebook_id()
        content = load_source_content()
        
        # Step 1: Get available transformations
        transformations = get_transformations()
        
        # Get random transformation
        transformation_id = get_random_transformation(transformations)
        
        # Step 2: Get existing sources
        existing_sources = get_existing_sources(notebook_id)
        
        # Step 3: Delete existing sources
        delete_existing_sources(existing_sources, notebook_id)
        
        # Step 4: Create new text source
        source_id = create_text_source(notebook_id, content, transformation_id)
        
        # Step 5: Verify final setup
        verify_final_setup(notebook_id)
        
        print_colored("\nSource setup completed successfully!", Colors.GREEN)
        print_colored(f"Notebook ID: {notebook_id}", Colors.GREEN)
        print_colored(f"Source ID: {source_id}", Colors.GREEN)
        print_colored(f"Transformation ID: {transformation_id}", Colors.GREEN)
        
    except KeyboardInterrupt:
        print_colored("\nProcess interrupted by user", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        print_colored(f"Unexpected error: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()