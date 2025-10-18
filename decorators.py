import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes
from config import Config
from supabase_client import db

logger = logging.getLogger(__name__)

def admin_required(func):
    """Decorator to ensure only admins can access certain functions"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in Config.ADMIN_USER_IDS:
            await update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذه الميزة.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def channel_owner_required(func):
    """Decorator to ensure user owns the channel they're trying to modify"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        # This will be used in callback handlers where channel_id is in callback_data
        query = update.callback_query
        if query and query.data:
            try:
                # Extract channel_id from callback_data (format: "action_channelid")
                parts = query.data.split('_')
                if len(parts) >= 2:
                    channel_id = int(parts[1])
                    
                    # Check if user owns this channel
                    channel = await db.get_channel_by_id(channel_id)
                    if not channel or channel['user_owner_id'] != update.effective_user.id:
                        await query.answer("❌ ليس لديك صلاحية للوصول إلى هذه القناة.")
                        return
            except (ValueError, IndexError):
                await query.answer("❌ خطأ في البيانات.")
                return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

def log_user_action(action: str):
    """Decorator to log user actions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(f"User {user_id} (@{username}) performed action: {action}")
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator

def handle_errors(func):
    """Decorator to handle and log errors gracefully"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            
            # Send user-friendly error message
            error_message = "❌ حدث خطأ غير متوقع. يرجى المحاولة لاحقاً."
            
            if update.message:
                await update.message.reply_text(error_message)
            elif update.callback_query:
                await update.callback_query.answer(error_message, show_alert=True)
    return wrapper