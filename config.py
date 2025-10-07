import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Flask Configuration
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')
    
    # Base directories
    BASE_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_data')
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    
    # Cache Configuration
    CACHE_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache')
    CACHE_TIMEOUT = 3600  # 1 hour
    
    # API Keys
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # Quiz Generation Configuration
    DEFAULT_BATCH_SIZE = 7
    DEFAULT_SIMILARITY_THRESHOLD = 0.85
    MAX_QUESTIONS_PER_QUIZ = 50
    
    # Temporary File Management
    TEMP_FILE_EXPIRY = 3600  # 1 hour
    
    @staticmethod
    def get_user_base_folder(user_id):
        """Get the base folder path for a specific user."""
        return os.path.join(Config.BASE_DATA_DIR, user_id)
    
    @staticmethod
    def get_user_data_folder(user_id):
        """Get the data_files folder path for a specific user."""
        return os.path.join(Config.BASE_DATA_DIR, user_id, f'data_files_{user_id}')
    
    @staticmethod
    def get_user_vectordb_folder(user_id):
        """Get the vector_db folder path for a specific user."""
        return os.path.join(Config.BASE_DATA_DIR, user_id, f'vector_db_{user_id}')
    
    @staticmethod
    def get_user_state_file(user_id):
        """Get the processed_files.json path for a specific user."""
        return os.path.join(Config.BASE_DATA_DIR, user_id, f'processed_files_{user_id}.json')