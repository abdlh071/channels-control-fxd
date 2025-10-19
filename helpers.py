import re
import pytz
from datetime import datetime, time, timedelta
from croniter import croniter
from typing import Optional, Tuple
from config import Config

def is_valid_time_format(time_str: str) -> bool:
    """Check if time string is in valid HH:MM format"""
    pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
    return bool(re.match(pattern, time_str))

def parse_time_string(time_str: str) -> Optional[time]:
    """Parse time string to time object"""
    if not is_valid_time_format(time_str):
        return None
    
    try:
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    except ValueError:
        return None

def get_next_occurrence(cron_expression: str, timezone_str: str = None) -> Optional[datetime]:
    """Get the next occurrence of a cron expression"""
    try:
        tz = pytz.timezone(timezone_str or Config.TIMEZONE)
        now = datetime.now(tz)
        
        # Create croniter instance
        cron = croniter(cron_expression, now)
        next_run = cron.get_next(datetime)
        
        return next_run
    except Exception:
        return None

def create_cron_expression(schedule_type: str, time_obj: time = None, weekday: int = None) -> Optional[str]:
    """Create cron expression based on schedule type"""
    if not time_obj:
        time_obj = time(12, 0)  # Default to noon
    
    minute = time_obj.minute
    hour = time_obj.hour
    
    if schedule_type == "daily":
        return f"{minute} {hour} * * *"
    elif schedule_type == "weekly" and weekday is not None:
        return f"{minute} {hour} * * {weekday}"
    elif schedule_type == "2days":
        return f"{minute} {hour} */2 * *"
    
    return None

def validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression"""
    try:
        # Test if croniter can parse it
        cron = croniter(cron_expr)
        # Try to get next occurrence
        cron.get_next()
        return True
    except Exception:
        return False

def format_datetime_arabic(dt: datetime) -> str:
    """Format datetime in Arabic-friendly format"""
    if dt.tzinfo is None:
        tz = pytz.timezone(Config.TIMEZONE)
        dt = tz.localize(dt)
    else:
        tz = pytz.timezone(Config.TIMEZONE)
        dt = dt.astimezone(tz)
    
    weekdays_ar = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']
    months_ar = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
                 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
    
    weekday = weekdays_ar[dt.weekday()]
    month = months_ar[dt.month - 1]
    
    return f"{weekday} {dt.day} {month} {dt.year} - {dt.strftime('%H:%M')}"

def get_weekday_name(weekday_num: int) -> str:
    """Get Arabic weekday name"""
    weekdays_ar = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']
    return weekdays_ar[weekday_num] if 0 <= weekday_num <= 6 else 'غير محدد'

def truncate_text(text: str, max_length: int = 50) -> str:
    """Truncate text to specified length"""
    if not text:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text

def escape_markdown(text: str) -> str:
    """Escape markdown special characters"""
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text

def is_media_message(message) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if message contains media and return type and file_id - enhanced version"""
    try:
        if hasattr(message, 'photo') and message.photo:
            return True, "photo", message.photo[-1].file_id
        elif hasattr(message, 'video') and message.video:
            return True, "video", message.video.file_id
        elif hasattr(message, 'document') and message.document:
            return True, "document", message.document.file_id
        elif hasattr(message, 'audio') and message.audio:
            return True, "audio", message.audio.file_id
        elif hasattr(message, 'voice') and message.voice:
            return True, "voice", message.voice.file_id
        elif hasattr(message, 'video_note') and message.video_note:
            return True, "video_note", message.video_note.file_id
        elif hasattr(message, 'sticker') and message.sticker:
            return True, "sticker", message.sticker.file_id
        elif hasattr(message, 'animation') and message.animation:
            return True, "animation", message.animation.file_id
        else:
            return False, None, None
    except AttributeError as e:
        # Log the error but don't crash
        import logging
        logging.getLogger(__name__).debug(f"Error checking media message: {e}")
        return False, None, None

def is_forwarded_from_channel(message) -> Tuple[bool, Optional[str], Optional[int]]:
    """Enhanced check if message is forwarded from a channel/group"""
    try:
        # Method 1: Direct forward from channel
        if hasattr(message, 'forward_from_chat') and message.forward_from_chat is not None:
            chat = message.forward_from_chat
            if chat.type in ['channel', 'supergroup']:
                return True, getattr(chat, 'title', 'قناة غير محددة'), chat.id
        
        # Method 2: Check sender_chat (for posts sent on behalf of channels)
        if hasattr(message, 'sender_chat') and message.sender_chat is not None:
            chat = message.sender_chat
            if chat.type in ['channel', 'supergroup']:
                return True, getattr(chat, 'title', 'قناة غير محددة'), chat.id
        
        # Method 3: Check for automatic forwards from linked channels
        if hasattr(message, 'is_automatic_forward') and message.is_automatic_forward:
            # For automatic forwards, the chat info might be in the message chat itself
            if hasattr(message, 'chat') and message.chat.type in ['channel', 'supergroup']:
                return True, getattr(message.chat, 'title', 'قناة غير محددة'), message.chat.id
        
        return False, None, None
        
    except AttributeError as e:
        import logging
        logging.getLogger(__name__).debug(f"Error checking forwarded from channel: {e}")
        return False, None, None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Unexpected error in is_forwarded_from_channel: {e}")
        return False, None, None

def log_message_details(message, logger):
    """Log detailed message information for debugging"""
    try:
        details = []
        
        # Basic message info
        details.append(f"Message ID: {getattr(message, 'message_id', 'N/A')}")
        details.append(f"Date: {getattr(message, 'date', 'N/A')}")
        details.append(f"Chat Type: {getattr(message.chat, 'type', 'N/A')}")
        
        # Forward information
        forward_info = []
        forward_attrs = [
            'forward_from', 'forward_from_chat', 'forward_sender_name',
            'forward_date', 'is_automatic_forward', 'sender_chat'
        ]
        
        for attr in forward_attrs:
            if hasattr(message, attr):
                value = getattr(message, attr)
                if value is not None:
                    if hasattr(value, 'id'):
                        forward_info.append(f"{attr}: {getattr(value, 'title', getattr(value, 'first_name', 'N/A'))} (ID: {value.id}, Type: {getattr(value, 'type', 'N/A')})")
                    else:
                        forward_info.append(f"{attr}: {value}")
        
        if forward_info:
            details.append(f"Forward info: {'; '.join(forward_info)}")
        else:
            details.append("Forward info: غير معاد توجيهها")
        
        # Media information
        has_media, media_type, file_id = is_media_message(message)
        if has_media:
            details.append(f"Media: {media_type} (File ID: {file_id[:20]}...)")
        else:
            details.append("Media: بدون ميديا")
        
        # Text content
        text_content = getattr(message, 'text', None) or getattr(message, 'caption', None)
        if text_content:
            details.append(f"Text: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
        
        logger.info(f"Message details: {' | '.join(details)}")
        
    except Exception as e:
        logger.error(f"Error logging message details: {e}")

def format_schedule_info(cron_expr: str, next_run: datetime) -> str:
    """Format schedule information for display"""
    schedule_desc = "غير محدد"
    
    if cron_expr == "0 * * * *":
        schedule_desc = "كل ساعة"
    elif cron_expr.endswith(" * * *"):
        parts = cron_expr.split()
        if len(parts) >= 2:
            schedule_desc = f"يومياً في {parts[1]}:{parts[0]:0>2}"
    elif " * * " in cron_expr and cron_expr.count("*") == 3:
        parts = cron_expr.split()
        if len(parts) >= 5:
            weekday_num = int(parts[4])
            weekday = get_weekday_name(weekday_num)
            schedule_desc = f"كل {weekday} في {parts[1]}:{parts[0]:0>2}"
    elif "*/2 * *" in cron_expr:
        parts = cron_expr.split()
        schedule_desc = f"كل يومين في {parts[1]}:{parts[0]:0>2}"
    
    next_run_formatted = format_datetime_arabic(next_run)
    
    return f"📅 النوع: {schedule_desc}\n⏰ الموعد القادم: {next_run_formatted}"

def sanitize_channel_name(name: str) -> str:
    """Sanitize channel name for display"""
    if not name:
        return "قناة غير محددة"
    
    # Remove @ symbol and clean up the name
    name = str(name).replace('@', '')
    # Limit length
    return truncate_text(name, 30)

def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def get_media_caption(message) -> Optional[str]:
    """Get caption from media message"""
    try:
        if hasattr(message, 'caption') and message.caption:
            return message.caption
        return None
    except AttributeError:
        return None

def create_once_schedule(target_datetime: datetime) -> Tuple[str, datetime]:
    """Create a one-time schedule cron expression"""
    # For one-time schedules, we'll use a specific cron that matches the exact time
    # But since cron doesn't support year/date, we'll handle this differently in the scheduler
    cron_expr = f"{target_datetime.minute} {target_datetime.hour} {target_datetime.day} {target_datetime.month} *"
    return cron_expr, target_datetime

def parse_datetime_input(date_str: str, time_str: str, timezone_str: str = None) -> Optional[datetime]:
    """Parse date and time input strings into datetime object"""
    try:
        tz = pytz.timezone(timezone_str or Config.TIMEZONE)
        
        # Parse date (DD/MM/YYYY or DD-MM-YYYY)
        date_str = date_str.replace('-', '/').replace('.', '/')
        day, month, year = map(int, date_str.split('/'))
        
        # Parse time
        time_obj = parse_time_string(time_str)
        if not time_obj:
            return None
        
        # Create datetime
        dt = datetime.combine(datetime(year, month, day).date(), time_obj)
        dt = tz.localize(dt)
        
        return dt
    except (ValueError, IndexError):
        return None

def debug_message_forwarding(message) -> dict:
    """Debug function to check all forwarding-related attributes of a message"""
    debug_info = {
        'is_forwarded': False,
        'forward_type': None,
        'source_chat': None,
        'source_chat_id': None,
        'source_chat_type': None,
        'attributes_found': [],
        'all_attributes': []
    }
    
    try:
        # List all attributes
        all_attrs = [attr for attr in dir(message) if not attr.startswith('_')]
        debug_info['all_attributes'] = all_attrs
        
        # Check forwarding attributes
        forward_attrs = {
            'forward_from_chat': 'channel/group forward',
            'forward_from': 'user forward',
            'forward_sender_name': 'anonymous forward',
            'forward_date': 'forwarded message',
            'is_automatic_forward': 'automatic forward',
            'sender_chat': 'sent on behalf of'
        }
        
        for attr, desc in forward_attrs.items():
            if hasattr(message, attr):
                value = getattr(message, attr)
                if value is not None:
                    debug_info['attributes_found'].append(f"{attr}: {desc}")
                    debug_info['is_forwarded'] = True
                    
                    # Try to extract chat info
                    if hasattr(value, 'id') and hasattr(value, 'type'):
                        if value.type in ['channel', 'supergroup']:
                            debug_info['source_chat'] = getattr(value, 'title', 'N/A')
                            debug_info['source_chat_id'] = value.id
                            debug_info['source_chat_type'] = value.type
                            debug_info['forward_type'] = attr
        
        return debug_info
        
    except Exception as e:
        debug_info['error'] = str(e)
        return debug_info

def get_channel_from_message(message):
    """Extract channel information from any type of message - comprehensive version"""
    try:
        # Priority order for getting channel info:
        
        # 1. Forward from chat (most reliable for forwarded messages)
        if hasattr(message, 'forward_from_chat') and message.forward_from_chat:
            chat = message.forward_from_chat
            if chat.type in ['channel', 'supergroup']:
                return chat
        
        # 2. Sender chat (for messages sent on behalf of channels)
        if hasattr(message, 'sender_chat') and message.sender_chat:
            chat = message.sender_chat
            if chat.type in ['channel', 'supergroup']:
                return chat
        
        # 3. For automatic forwards, check the current chat
        if hasattr(message, 'is_automatic_forward') and message.is_automatic_forward:
            if hasattr(message, 'chat') and message.chat.type in ['channel', 'supergroup']:
                return message.chat
        
        # 4. Direct chat (if the message is in a channel/group directly)
        if hasattr(message, 'chat') and message.chat.type in ['channel', 'supergroup']:
            # Only return this if we have some indication it's meant for channel addition
            # (e.g., if there's a forward_date, meaning it was forwarded somehow)
            if hasattr(message, 'forward_date') and message.forward_date:
                return message.chat
        
        return None
        
    except AttributeError as e:
        import logging
        logging.getLogger(__name__).debug(f"Error getting channel from message: {e}")
        return None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Unexpected error getting channel from message: {e}")
        return None