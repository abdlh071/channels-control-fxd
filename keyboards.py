from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Any

class Keyboards:
    @staticmethod
    def main_menu():
        """Main menu keyboard for regular users"""
        keyboard = [
            [KeyboardButton("➕ إضافة قناة جديدة")],
            [KeyboardButton("📁 قنواتي ومنشوراتي")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    @staticmethod
    def admin_menu():
        """Admin panel keyboard"""
        keyboard = [
            [InlineKeyboardButton("📊 إحصائيات عامة", callback_data="admin_stats")],
            [InlineKeyboardButton("👁️ عرض جميع القنوات", callback_data="admin_channels")],
            [InlineKeyboardButton("📣 إرسال رسالة عامة", callback_data="admin_broadcast")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def user_channels(channels: List[Dict[str, Any]]):
        """Display user's channels"""
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(
                f"📺 {channel['channel_name']}", 
                callback_data=f"channel_{channel['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def channel_management(channel_id: int):
        """Channel management menu"""
        keyboard = [
            [InlineKeyboardButton("📝 عرض/تعديل المنشورات", callback_data=f"posts_{channel_id}")],
            [InlineKeyboardButton("➕ إنشاء منشور جديد", callback_data=f"new_post_{channel_id}")],
            [InlineKeyboardButton("⏰ إعدادات الجدولة", callback_data=f"schedule_{channel_id}")],
            [InlineKeyboardButton("🗑️ حذف القناة من البوت", callback_data=f"delete_channel_{channel_id}")],
            [InlineKeyboardButton("🔙 رجوع للقنوات", callback_data="my_channels")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def channel_posts(posts: List[Dict[str, Any]], channel_id: int):
        """Display channel posts with actions"""
        keyboard = []
        for post in posts:
            content_preview = post['post_content'][:30] + "..." if post['post_content'] and len(post['post_content']) > 30 else post['post_content']
            if not content_preview:
                content_preview = f"[{post['media_type']}]" if post['media_type'] else "[منشور فارغ]"
            
            keyboard.append([InlineKeyboardButton(
                f"📄 {content_preview}",
                callback_data=f"post_{post['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("➕ إنشاء منشور جديد", callback_data=f"new_post_{channel_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع لإدارة القناة", callback_data=f"channel_{channel_id}")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def post_actions(post_id: int, channel_id: int):
        """Post action menu"""
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل", callback_data=f"edit_post_{post_id}")],
            [InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_post_{post_id}")],
            [InlineKeyboardButton("⏰ جدولة", callback_data=f"schedule_post_{post_id}")],
            [InlineKeyboardButton("🔙 رجوع للمنشورات", callback_data=f"posts_{channel_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def schedule_options(post_id: int):
        """Schedule timing options"""
        keyboard = [
            [InlineKeyboardButton("مرة واحدة", callback_data=f"sched_once_{post_id}")],
            [InlineKeyboardButton("يومياً", callback_data=f"sched_daily_{post_id}")],
            [InlineKeyboardButton("أسبوعياً", callback_data=f"sched_weekly_{post_id}")],
            [InlineKeyboardButton("كل يومين", callback_data=f"sched_2days_{post_id}")],
            [InlineKeyboardButton("مخصص (Cron)", callback_data=f"sched_custom_{post_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data=f"post_{post_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def confirm_delete(item_type: str, item_id: int):
        """Confirmation for delete actions"""
        keyboard = [
            [InlineKeyboardButton("✅ نعم، احذف", callback_data=f"confirm_delete_{item_type}_{item_id}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_delete_{item_type}_{item_id}")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_channels(channels: List[Dict[str, Any]]):
        """Admin view of all channels"""
        keyboard = []
        for channel in channels:
            status = "🚫" if channel['is_banned'] else "⭐️" if channel['is_vip'] else "📺"
            keyboard.append([InlineKeyboardButton(
                f"{status} {channel['channel_name']}",
                callback_data=f"admin_channel_{channel['id']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 لوحة التحكم", callback_data="admin_menu")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def admin_channel_actions(channel_id: int, is_banned: bool, is_vip: bool):
        """Admin actions for a specific channel"""
        keyboard = []
        
        # Ban/Unban button
        ban_text = "✅ إلغاء الحظر" if is_banned else "🚫 حظر القناة"
        keyboard.append([InlineKeyboardButton(ban_text, callback_data=f"admin_ban_{channel_id}_{not is_banned}")])
        
        # VIP/Remove VIP button
        vip_text = "❌ إزالة VIP" if is_vip else "⭐️ تفعيل VIP"
        keyboard.append([InlineKeyboardButton(vip_text, callback_data=f"admin_vip_{channel_id}_{not is_vip}")])
        
        # View posts
        keyboard.append([InlineKeyboardButton("📄 عرض المنشورات", callback_data=f"admin_posts_{channel_id}")])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع للقنوات", callback_data="admin_channels")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def broadcast_confirm(message_preview: str):
        """Confirm broadcast message"""
        keyboard = [
            [InlineKeyboardButton("✅ إرسال للجميع", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_action():
        """Cancel current action"""
        keyboard = [
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_action")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_main():
        """Simple back to main menu button"""
        keyboard = [
            [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def time_input_help():
        """Help keyboard for time input"""
        keyboard = [
            [KeyboardButton("12:00"), KeyboardButton("18:00"), KeyboardButton("09:00")],
            [KeyboardButton("15:30"), KeyboardButton("21:00"), KeyboardButton("06:00")],
            [KeyboardButton("❌ إلغاء")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    @staticmethod
    def weekday_selection():
        """Weekday selection for weekly scheduling"""
        keyboard = [
            [InlineKeyboardButton("الأحد", callback_data="weekday_0")],
            [InlineKeyboardButton("الإثنين", callback_data="weekday_1")],
            [InlineKeyboardButton("الثلاثاء", callback_data="weekday_2")],
            [InlineKeyboardButton("الأربعاء", callback_data="weekday_3")],
            [InlineKeyboardButton("الخميس", callback_data="weekday_4")],
            [InlineKeyboardButton("الجمعة", callback_data="weekday_5")],
            [InlineKeyboardButton("السبت", callback_data="weekday_6")]
        ]
        return InlineKeyboardMarkup(keyboard)