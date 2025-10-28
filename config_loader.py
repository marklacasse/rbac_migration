"""
Configuration utility for loading environment variables from .env file.
"""
import os

def load_config():
    """
    Load configuration from .env file.
    Returns a dictionary with all the required configuration values.
    """
    config = {}
    
    # Try to load from .env file first
    env_file_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file_path):
        with open(env_file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    
    # Fall back to environment variables if not found in .env file
    required_keys = ['API_KEY', 'BASE_URL', 'AUTH', 'ORG']
    for key in required_keys:
        if key not in config:
            config[key] = os.getenv(key)
    
    # Add optional LOG_DIR with default value
    if 'LOG_DIR' not in config:
        config['LOG_DIR'] = os.getenv('LOG_DIR', 'Results')
    
    # Validate that all required values are present
    missing_vars = [key for key in required_keys if not config.get(key)]
    if missing_vars:
        raise ValueError("Missing required environment variables: {}".format(', '.join(missing_vars)))
    
    return config

def get_headers(config):
    """
    Generate standard headers for API requests.
    """
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': config['AUTH'],
        'API-Key': config['API_KEY']
    }