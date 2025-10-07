import os
import shutil
import json
from config import Config

def create_user_directories(user_id):
    """Create user-specific directories for data files and vector database."""
    # Create user base folder first
    user_base_folder = Config.get_user_base_folder(user_id)
    data_folder = Config.get_user_data_folder(user_id)
    vectordb_folder = Config.get_user_vectordb_folder(user_id)
    
    # Create directories if they don't exist
    os.makedirs(user_base_folder, exist_ok=True)
    os.makedirs(data_folder, exist_ok=True)
    os.makedirs(vectordb_folder, exist_ok=True)
    
    return data_folder, vectordb_folder

def delete_user_data(user_id):
    """Delete all user-specific data."""
    user_base_folder = Config.get_user_base_folder(user_id)
    
    # Remove the entire user folder
    if os.path.exists(user_base_folder):
        shutil.rmtree(user_base_folder)

def get_user_processed_files(user_id):
    """Get the processed files state for a user."""
    state_file = Config.get_user_state_file(user_id)
    
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return json.load(f)
    return {}

def save_user_processed_files(user_id, processed_files):
    """Save the processed files state for a user."""
    state_file = Config.get_user_state_file(user_id)
    
    with open(state_file, 'w') as f:
        json.dump(processed_files, f)

def list_user_files(user_id):
    """List all PDF and DOCX files for a user."""
    import glob
    data_folder = Config.get_user_data_folder(user_id)
    
    if not os.path.exists(data_folder):
        return []
    
    pdf_files = glob.glob(f"{data_folder}/*.pdf")
    docx_files = glob.glob(f"{data_folder}/*.docx")
    
    return pdf_files + docx_files