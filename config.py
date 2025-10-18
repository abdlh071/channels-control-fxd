import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Telegram Bot Settings
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_USER_IDS = [int(id.strip()) for id in os.getenv('ADMIN_USER_IDS', '').split(',') if id.strip()]
    
    # Supabase Settings
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Server Settings
    ALIVE_URL = os.getenv('ALIVE_URL')
    PORT = int(os.getenv('PORT', 8080))
    TIMEZONE = os.getenv('TIMEZONE', 'Africa/Algiers')
    
    # Logging Settings
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate that all required environment variables are set"""
        required_vars = {
            'BOT_TOKEN': cls.BOT_TOKEN,
            'SUPABASE_URL': cls.SUPABASE_URL,
            'SUPABASE_KEY': cls.SUPABASE_KEY,
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        if not cls.ADMIN_USER_IDS:
            raise ValueError("ADMIN_USER_IDS must contain at least one valid user ID")
        
        return True

# Configure logging
def setup_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO),
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Set specific loggers
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('supabase').setLevel(logging.INFO)
    
    return logging.getLogger(__name__)