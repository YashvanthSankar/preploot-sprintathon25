import json
import os
import time
from config import Config

class CacheManager:
    def __init__(self):
        self.cache_dir = Config.CACHE_FOLDER
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _get_cache_path(self, cache_id):
        return os.path.join(self.cache_dir, f"{cache_id}.json")
    
    def save_to_cache(self, data, cache_id):
        """Save data to cache with timestamp."""
        cache_data = {
            'timestamp': time.time(),
            'data': data
        }
        
        with open(self._get_cache_path(cache_id), 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    def get_from_cache(self, cache_id):
        """Get data from cache if not expired."""
        cache_path = self._get_cache_path(cache_id)
        
        if not os.path.exists(cache_path):
            return None
            
        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            
        # Check if cache is expired
        if time.time() - cache_data['timestamp'] > Config.CACHE_TIMEOUT:
            os.remove(cache_path)
            return None
            
        return cache_data['data']
    
    def clear_expired_cache(self):
        """Remove expired cache files."""
        current_time = time.time()
        
        for filename in os.listdir(self.cache_dir):
            if not filename.endswith('.json'):
                continue
                
            file_path = os.path.join(self.cache_dir, filename)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                if current_time - cache_data['timestamp'] > Config.CACHE_TIMEOUT:
                    os.remove(file_path)
            except (json.JSONDecodeError, KeyError, OSError):
                # Remove corrupted cache files
                os.remove(file_path)