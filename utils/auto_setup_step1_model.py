#!/usr/bin/env python3
"""
Script to setup AI models via API:
1. Get existing models
2. Delete old models with same names
3. Create new embedding and LLM models
4. Set them as default models
"""

import requests
import json
import sys
from typing import Dict, List, Optional

# Configuration
API_BASE = "http://localhost:4427/api"
AUTH_TOKEN = "1234567890"
EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "Qwen/Qwen2.5-32B-Instruct"

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

def get_existing_models() -> List[Dict]:
    """Get list of existing models"""
    print_colored("Step 1: Getting existing models...", Colors.YELLOW)
    models = make_request('GET', '/models')
    
    print("Current models:")
    print(json.dumps(models, indent=2))
    print()
    
    return models

def delete_existing_models(models: List[Dict]):
    """Delete existing models with same names"""
    print_colored("Step 2: Deleting existing models...", Colors.YELLOW)
    
    # Find models to delete
    embedding_model_id = None
    llm_model_id = None
    
    for model in models:
        if model.get('name') == EMBEDDING_MODEL and model.get('type') == 'embedding':
            embedding_model_id = model.get('id')
        elif model.get('name') == LLM_MODEL and model.get('type') == 'language':
            llm_model_id = model.get('id')
    
    # Delete embedding model if exists
    if embedding_model_id:
        print(f"Deleting existing embedding model: {embedding_model_id}")
        delete_response = make_request('DELETE', f'/models/{embedding_model_id}')
        print(f"Delete response: {delete_response}")
    else:
        print("No existing embedding model found to delete")
    
    # Delete LLM model if exists
    if llm_model_id:
        print(f"Deleting existing LLM model: {llm_model_id}")
        delete_response = make_request('DELETE', f'/models/{llm_model_id}')
        print(f"Delete response: {delete_response}")
    else:
        print("No existing LLM model found to delete")
    
    print()

def create_embedding_model() -> str:
    """Create new embedding model and return its ID"""
    print_colored("Step 3: Creating new embedding model...", Colors.YELLOW)
    
    data = {
        "name": EMBEDDING_MODEL,
        "provider": "openai",
        "type": "embedding",
    }
    
    response = make_request('POST', '/models', data)
    print("Embedding model creation response:")
    print(json.dumps(response, indent=2))
    
    model_id = response.get('id')
    if not model_id:
        print_colored("Failed to create embedding model", Colors.RED)
        sys.exit(1)
    
    print_colored(f"Created embedding model with ID: {model_id}", Colors.GREEN)
    print()
    
    return model_id

def create_llm_model() -> str:
    """Create new LLM model and return its ID"""
    print_colored("Step 4: Creating new LLM model...", Colors.YELLOW)
    
    data = {
        "name": LLM_MODEL,
        "provider": "openrouter",
        "type": "language"
    }
    
    response = make_request('POST', '/models', data)
    print("LLM model creation response:")
    print(json.dumps(response, indent=2))
    
    model_id = response.get('id')
    if not model_id:
        print_colored("Failed to create LLM model", Colors.RED)
        sys.exit(1)
    
    print_colored(f"Created LLM model with ID: {model_id}", Colors.GREEN)
    print()
    
    return model_id

def set_default_models(embedding_id: str, llm_id: str):
    """Set models as default"""
    print_colored("Step 5: Setting models as default...", Colors.YELLOW)
    
    data = {
        "default_chat_model": llm_id,
        "default_transformation_model": llm_id,
        "large_context_model": llm_id,
        "default_text_to_speech_model": None,
        "default_speech_to_text_model": None,
        "default_embedding_model": embedding_id,
        "default_tools_model": llm_id
    }
    
    response = make_request('PUT', '/models/defaults', data)
    print("Default models setting response:")
    print(json.dumps(response, indent=2))
    print()

def verify_final_setup():
    """Verify final setup by getting models list"""
    print_colored("Step 6: Verifying final setup...", Colors.YELLOW)
    
    models = make_request('GET', '/models')
    print("Final models list:")
    print(json.dumps(models, indent=2))

def main():
    """Main function to orchestrate the model setup process"""
    print_colored("Starting model setup process...\n", Colors.BLUE)
    
    try:
        # Step 1: Get existing models
        existing_models = get_existing_models()
        
        # Step 2: Delete existing models with same names
        delete_existing_models(existing_models)
        
        # Step 3: Create new embedding model
        embedding_id = create_embedding_model()
        
        # Step 4: Create new LLM model
        llm_id = create_llm_model()
        
        # Step 5: Set as default models
        set_default_models(embedding_id, llm_id)
        
        # Step 6: Verify final setup
        verify_final_setup()
        
        print_colored("\nModel setup completed successfully!", Colors.GREEN)
        print_colored(f"Embedding Model ID: {embedding_id}", Colors.GREEN)
        print_colored(f"LLM Model ID: {llm_id}", Colors.GREEN)
        
    except KeyboardInterrupt:
        print_colored("\nProcess interrupted by user", Colors.YELLOW)
        sys.exit(0)
    except Exception as e:
        print_colored(f"Unexpected error: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()