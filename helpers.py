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
    """Check if message contains media and return type and file_id"""
    if message.photo:
        return True, "photo", message.photo[-1].file_id
    elif message.video:
        return True, "video", message.video.file_id
    elif message.document:
        return True, "document", message.document.file_id
    elif message.audio:
        return True, "audio", message.audio.file_id
    elif message.voice:
        return True, "voice", message.voice.file_id
    elif message.video_note:
        return True, "video_note", message.video_note.file_id
    elif message.sticker:
        return True, "sticker", message.sticker.file_id
    else:
        return False, None, None

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
    # Remove @ symbol and clean up the name
    name = name.replace('@', '')
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
    if hasattr(message, 'caption') and message.caption:
        return message.caption
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