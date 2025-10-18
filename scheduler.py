import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from croniter import croniter
import pytz
from supabase_client import db
from config import Config
from helpers import (
    get_next_occurrence, format_datetime_arabic, 
    is_media_message, truncate_text
)

logger = logging.getLogger(__name__)

class PostScheduler:
    def __init__(self, bot_context: ContextTypes.DEFAULT_TYPE):
        self.bot_context = bot_context
        self.timezone = pytz.timezone(Config.TIMEZONE)
        self.is_running = False
        self.check_interval = 60  # Check every minute
    
    async def start_scheduler(self):
        """Start the scheduler loop"""
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        logger.info("Post scheduler started")
        
        while self.is_running:
            try:
                await self.check_and_execute_schedules()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    def stop_scheduler(self):
        """Stop the scheduler"""
        self.is_running = False
        logger.info("Post scheduler stopped")
    
    async def check_and_execute_schedules(self):
        """Check for due schedules and execute them"""
        try:
            due_schedules = await db.get_due_schedules()
            
            if not due_schedules:
                return
            
            logger.info(f"Found {len(due_schedules)} due schedules")
            
            for schedule in due_schedules:
                await self.process_schedule(schedule)
                
        except Exception as e:
            logger.error(f"Error checking schedules: {e}", exc_info=True)
    
    async def process_schedule(self, schedule: Dict[str, Any]):
        """Process a single schedule"""
        try:
            schedule_id = schedule['id']
            post_id = schedule['post_id']
            channel_tg_id = schedule['channel_tg_id']
            user_id = schedule['user_id']
            cron_expression = schedule['cron_expression']
            
            logger.info(f"Processing schedule {schedule_id} for post {post_id}")
            
            # Immediately deactivate the schedule to prevent double execution
            await db.deactivate_schedule(schedule_id)
            
            # Get post data
            post = await db.get_post_by_id(post_id)
            if not post:
                logger.error(f"Post {post_id} not found for schedule {schedule_id}")
                return
            
            # Get channel data
            channel = await db.get_channel_by_tg_id(channel_tg_id)
            if not channel:
                logger.error(f"Channel {channel_tg_id} not found for schedule {schedule_id}")
                return
            
            # Check if channel is banned
            if channel['is_banned']:
                logger.info(f"Skipping banned channel {channel_tg_id}")
                await self.notify_user(user_id, f"⚠️ تم تخطي النشر في القناة المحظورة '{channel['channel_name']}'.")
                return
            
            # Execute the post
            success = await self.send_post_to_channel(post, channel_tg_id)
            
            if success:
                # Notify user of success
                await self.notify_user(
                    user_id, 
                    f"✅ تم إرسال منشورك بنجاح إلى قناة '{channel['channel_name']}'."
                )
                
                # Calculate next run time for recurring schedules
                next_run = self.calculate_next_run(cron_expression)
                
                if next_run:
                    # Reactivate schedule with new time
                    new_schedule_id = await db.add_schedule(
                        post_id, channel_tg_id, user_id, cron_expression, next_run
                    )
                    
                    if new_schedule_id:
                        logger.info(f"Rescheduled post {post_id} for {next_run}")
                    else:
                        logger.error(f"Failed to reschedule post {post_id}")
                else:
                    # One-time schedule, delete it
                    await db.delete_schedule(schedule_id)
                    logger.info(f"One-time schedule {schedule_id} completed and deleted")
            
            else:
                # Notify user of failure
                await self.notify_user(
                    user_id,
                    f"⚠️ فشل إرسال منشورك إلى قناة '{channel['channel_name']}'. "
                    "ربما تم إزالة البوت أو فقد الصلاحيات."
                )
                
                # Deactivate all schedules for this channel
                await db.deactivate_channel_schedules(channel_tg_id)
                
        except Exception as e:
            logger.error(f"Error processing schedule {schedule.get('id')}: {e}", exc_info=True)
    
    async def send_post_to_channel(self, post: Dict[str, Any], channel_tg_id: int) -> bool:
        """Send a post to a specific channel"""
        try:
            bot = self.bot_context.bot
            
            # Check if post has media
            if post['media_file_id'] and post['media_type']:
                # Send media with caption
                caption = post['post_content'] or ""
                
                if post['media_type'] == 'photo':
                    await bot.send_photo(
                        chat_id=channel_tg_id,
                        photo=post['media_file_id'],
                        caption=caption
                    )
                elif post['media_type'] == 'video':
                    await bot.send_video(
                        chat_id=channel_tg_id,
                        video=post['media_file_id'],
                        caption=caption
                    )
                elif post['media_type'] == 'document':
                    await bot.send_document(
                        chat_id=channel_tg_id,
                        document=post['media_file_id'],
                        caption=caption
                    )
                elif post['media_type'] == 'audio':
                    await bot.send_audio(
                        chat_id=channel_tg_id,
                        audio=post['media_file_id'],
                        caption=caption
                    )
                elif post['media_type'] == 'voice':
                    await bot.send_voice(
                        chat_id=channel_tg_id,
                        voice=post['media_file_id']
                    )
                elif post['media_type'] == 'video_note':
                    await bot.send_video_note(
                        chat_id=channel_tg_id,
                        video_note=post['media_file_id']
                    )
                elif post['media_type'] == 'sticker':
                    await bot.send_sticker(
                        chat_id=channel_tg_id,
                        sticker=post['media_file_id']
                    )
                else:
                    # Fallback to document
                    await bot.send_document(
                        chat_id=channel_tg_id,
                        document=post['media_file_id'],
                        caption=caption
                    )
            
            elif post['post_content']:
                # Send text message
                await bot.send_message(
                    chat_id=channel_tg_id,
                    text=post['post_content']
                )
            
            else:
                logger.error(f"Post {post['id']} has no content")
                return False
            
            logger.info(f"Successfully sent post {post['id']} to channel {channel_tg_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Telegram error sending post {post['id']} to channel {channel_tg_id}: {e}")
            
            # Check if it's a permissions error
            if "bot was blocked" in str(e).lower() or \
               "chat not found" in str(e).lower() or \
               "bot is not a member" in str(e).lower() or \
               "not enough rights" in str(e).lower():
                return False
            
            # For other errors, might be temporary
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending post {post['id']} to channel {channel_tg_id}: {e}")
            return False
    
    async def notify_user(self, user_id: int, message: str):
        """Send notification to user"""
        try:
            bot = self.bot_context.bot
            await bot.send_message(chat_id=user_id, text=message)
            logger.info(f"Notified user {user_id}: {truncate_text(message, 50)}")
            
        except TelegramError as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error notifying user {user_id}: {e}")
    
    def calculate_next_run(self, cron_expression: str) -> datetime:
        """Calculate next run time for a cron expression"""
        try:
            now = datetime.now(self.timezone)
            cron = croniter(cron_expression, now)
            next_run = cron.get_next(datetime)
            
            # Convert to timezone-aware datetime
            if next_run.tzinfo is None:
                next_run = self.timezone.localize(next_run)
            
            return next_run
            
        except Exception as e:
            logger.error(f"Error calculating next run for cron '{cron_expression}': {e}")
            return None
    
    def is_one_time_schedule(self, cron_expression: str) -> bool:
        """Check if a cron expression represents a one-time schedule"""
        # One-time schedules typically have specific date/month values
        # For simplicity, we'll check if it has specific date and month
        parts = cron_expression.split()
        if len(parts) >= 5:
            day = parts[2]
            month = parts[3]
            # If both day and month are specific numbers (not * or ranges)
            return day.isdigit() and month.isdigit()
        return False
    
    async def get_scheduler_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics"""
        try:
            active_schedules = await db.get_due_schedules()
            all_schedules_count = len(await db.get_user_schedules(0))  # This needs to be fixed
            
            return {
                'is_running': self.is_running,
                'check_interval': self.check_interval,
                'due_schedules': len(active_schedules),
                'timezone': Config.TIMEZONE,
                'last_check': datetime.now(self.timezone).isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {
                'is_running': self.is_running,
                'error': str(e)
            }

# Global scheduler instance (will be initialized in main.py)
scheduler = None