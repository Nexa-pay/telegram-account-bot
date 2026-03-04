import os
import logging

logger = logging.getLogger(__name__)

class Config:
    # Try to get from environment, with clear error messages
    API_ID = os.environ.get('API_ID')
    API_HASH = os.environ.get('API_HASH')
    BOT_TOKEN = os.environ.get('BOT_TOKEN')
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Admin user IDs (comma-separated)
    ADMIN_IDS = []
    admins_env = os.environ.get('ADMIN_IDS', '')
    if admins_env:
        try:
            ADMIN_IDS = [int(id.strip()) for id in admins_env.split(',') if id.strip()]
        except ValueError as e:
            logger.error(f"Error parsing ADMIN_IDS: {e}")
    
    @classmethod
    def validate(cls):
        """Validate that all required configs are present"""
        missing = []
        
        if not cls.API_ID:
            missing.append('API_ID')
        else:
            try:
                cls.API_ID = int(cls.API_ID)
            except ValueError:
                raise ValueError(f"API_ID must be an integer, got: {cls.API_ID}")
        
        if not cls.API_HASH:
            missing.append('API_HASH')
            
        if not cls.BOT_TOKEN:
            missing.append('BOT_TOKEN')
            
        if not cls.DATABASE_URL:
            missing.append('DATABASE_URL')
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}. "
                           f"Please set them in Railway dashboard.")
        
        return True