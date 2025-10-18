import logging
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from datetime import datetime
import pytz
from config import Config

logger = logging.getLogger(__name__)

class SupabaseClient:
    def __init__(self):
        self.supabase: Client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
        self.timezone = pytz.timezone(Config.TIMEZONE)
    
    # Channel Management
    async def add_channel(self, channel_tg_id: int, channel_name: str, user_owner_id: int) -> bool:
        """Add a new channel to the database"""
        try:
            response = self.supabase.table('channels').insert({
                'channel_tg_id': channel_tg_id,
                'channel_name': channel_name,
                'user_owner_id': user_owner_id,
                'is_vip': False,
                'is_banned': False
            }).execute()
            
            logger.info(f"Channel added: {channel_name} ({channel_tg_id}) by user {user_owner_id}")
            return True
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False
    
    async def get_user_channels(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all channels owned by a user"""
        try:
            response = self.supabase.table('channels').select('*').eq('user_owner_id', user_id).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting user channels: {e}")
            return []
    
    async def get_channel_by_tg_id(self, channel_tg_id: int) -> Optional[Dict[str, Any]]:
        """Get channel by Telegram ID"""
        try:
            response = self.supabase.table('channels').select('*').eq('channel_tg_id', channel_tg_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting channel by TG ID: {e}")
            return None
    
    async def get_channel_by_id(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Get channel by database ID"""
        try:
            response = self.supabase.table('channels').select('*').eq('id', channel_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting channel by ID: {e}")
            return None
    
    async def delete_channel(self, channel_id: int, user_id: int) -> bool:
        """Delete a channel (only by owner)"""
        try:
            response = self.supabase.table('channels').delete().eq('id', channel_id).eq('user_owner_id', user_id).execute()
            logger.info(f"Channel {channel_id} deleted by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            return False
    
    async def get_all_channels(self) -> List[Dict[str, Any]]:
        """Get all channels (admin only)"""
        try:
            response = self.supabase.table('channels').select('*').execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting all channels: {e}")
            return []
    
    async def update_channel_status(self, channel_id: int, is_banned: bool = None, is_vip: bool = None) -> bool:
        """Update channel status (admin only)"""
        try:
            update_data = {}
            if is_banned is not None:
                update_data['is_banned'] = is_banned
            if is_vip is not None:
                update_data['is_vip'] = is_vip
            
            response = self.supabase.table('channels').update(update_data).eq('id', channel_id).execute()
            logger.info(f"Channel {channel_id} status updated: {update_data}")
            return True
        except Exception as e:
            logger.error(f"Error updating channel status: {e}")
            return False
    
    # Post Management
    async def add_post(self, user_id: int, channel_id: int, post_content: str = None, 
                      media_file_id: str = None, media_type: str = None) -> Optional[int]:
        """Add a new post template"""
        try:
            response = self.supabase.table('posts').insert({
                'user_id': user_id,
                'channel_id': channel_id,
                'post_content': post_content,
                'media_file_id': media_file_id,
                'media_type': media_type
            }).execute()
            
            post_id = response.data[0]['id']
            logger.info(f"Post added: ID {post_id} by user {user_id}")
            return post_id
        except Exception as e:
            logger.error(f"Error adding post: {e}")
            return None
    
    async def get_channel_posts(self, channel_id: int, user_id: int) -> List[Dict[str, Any]]:
        """Get all posts for a channel by user"""
        try:
            response = self.supabase.table('posts').select('*').eq('channel_id', channel_id).eq('user_id', user_id).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting channel posts: {e}")
            return []
    
    async def get_post_by_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Get post by ID"""
        try:
            response = self.supabase.table('posts').select('*').eq('id', post_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting post by ID: {e}")
            return None
    
    async def update_post(self, post_id: int, user_id: int, post_content: str = None,
                         media_file_id: str = None, media_type: str = None) -> bool:
        """Update a post (only by owner)"""
        try:
            update_data = {}
            if post_content is not None:
                update_data['post_content'] = post_content
            if media_file_id is not None:
                update_data['media_file_id'] = media_file_id
            if media_type is not None:
                update_data['media_type'] = media_type
            
            response = self.supabase.table('posts').update(update_data).eq('id', post_id).eq('user_id', user_id).execute()
            logger.info(f"Post {post_id} updated by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating post: {e}")
            return False
    
    async def delete_post(self, post_id: int, user_id: int) -> bool:
        """Delete a post (only by owner)"""
        try:
            response = self.supabase.table('posts').delete().eq('id', post_id).eq('user_id', user_id).execute()
            logger.info(f"Post {post_id} deleted by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting post: {e}")
            return False
    
    # Schedule Management
    async def add_schedule(self, post_id: int, channel_tg_id: int, user_id: int,
                          cron_expression: str, next_run_at: datetime) -> Optional[int]:
        """Add a new schedule"""
        try:
            # Convert to UTC for storage
            if next_run_at.tzinfo is None:
                next_run_at = self.timezone.localize(next_run_at)
            next_run_at_utc = next_run_at.astimezone(pytz.UTC)
            
            response = self.supabase.table('schedule').insert({
                'post_id': post_id,
                'channel_tg_id': channel_tg_id,
                'user_id': user_id,
                'cron_expression': cron_expression,
                'next_run_at': next_run_at_utc.isoformat(),
                'is_active': True,
                'task_type': 'post'
            }).execute()
            
            schedule_id = response.data[0]['id']
            logger.info(f"Schedule added: ID {schedule_id} for post {post_id}")
            return schedule_id
        except Exception as e:
            logger.error(f"Error adding schedule: {e}")
            return None
    
    async def get_due_schedules(self) -> List[Dict[str, Any]]:
        """Get all schedules that are due for execution"""
        try:
            current_time = datetime.now(pytz.UTC).isoformat()
            response = self.supabase.table('schedule').select('*').eq('is_active', True).lte('next_run_at', current_time).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting due schedules: {e}")
            return []
    
    async def update_schedule_next_run(self, schedule_id: int, next_run_at: datetime) -> bool:
        """Update the next run time for a schedule"""
        try:
            # Convert to UTC for storage
            if next_run_at.tzinfo is None:
                next_run_at = self.timezone.localize(next_run_at)
            next_run_at_utc = next_run_at.astimezone(pytz.UTC)
            
            response = self.supabase.table('schedule').update({
                'next_run_at': next_run_at_utc.isoformat()
            }).eq('id', schedule_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error updating schedule next run: {e}")
            return False
    
    async def deactivate_schedule(self, schedule_id: int) -> bool:
        """Deactivate a schedule"""
        try:
            response = self.supabase.table('schedule').update({
                'is_active': False
            }).eq('id', schedule_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error deactivating schedule: {e}")
            return False
    
    async def delete_schedule(self, schedule_id: int) -> bool:
        """Delete a schedule"""
        try:
            response = self.supabase.table('schedule').delete().eq('id', schedule_id).execute()
            logger.info(f"Schedule {schedule_id} deleted")
            return True
        except Exception as e:
            logger.error(f"Error deleting schedule: {e}")
            return False
    
    async def get_user_schedules(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all schedules for a user"""
        try:
            response = self.supabase.table('schedule').select('*').eq('user_id', user_id).eq('is_active', True).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting user schedules: {e}")
            return []
    
    async def deactivate_channel_schedules(self, channel_tg_id: int) -> bool:
        """Deactivate all schedules for a channel (when bot is removed)"""
        try:
            response = self.supabase.table('schedule').update({
                'is_active': False
            }).eq('channel_tg_id', channel_tg_id).execute()
            
            logger.info(f"All schedules deactivated for channel {channel_tg_id}")
            return True
        except Exception as e:
            logger.error(f"Error deactivating channel schedules: {e}")
            return False
    
    # Broadcasting
    async def get_broadcast_channels(self) -> List[Dict[str, Any]]:
        """Get all channels eligible for broadcasting (non-VIP, non-banned)"""
        try:
            response = self.supabase.table('channels').select('*').eq('is_vip', False).eq('is_banned', False).execute()
            return response.data
        except Exception as e:
            logger.error(f"Error getting broadcast channels: {e}")
            return []
    
    # Statistics
    async def get_statistics(self) -> Dict[str, Any]:
        """Get general statistics (admin only)"""
        try:
            # Get total channels
            channels_response = self.supabase.table('channels').select('id', count='exact').execute()
            total_channels = channels_response.count
            
            # Get VIP channels
            vip_response = self.supabase.table('channels').select('id', count='exact').eq('is_vip', True).execute()
            vip_channels = vip_response.count
            
            # Get banned channels
            banned_response = self.supabase.table('channels').select('id', count='exact').eq('is_banned', True).execute()
            banned_channels = banned_response.count
            
            # Get total posts
            posts_response = self.supabase.table('posts').select('id', count='exact').execute()
            total_posts = posts_response.count
            
            # Get active schedules
            schedules_response = self.supabase.table('schedule').select('id', count='exact').eq('is_active', True).execute()
            active_schedules = schedules_response.count
            
            return {
                'total_channels': total_channels,
                'vip_channels': vip_channels,
                'banned_channels': banned_channels,
                'total_posts': total_posts,
                'active_schedules': active_schedules
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

# Global instance
db = SupabaseClient()