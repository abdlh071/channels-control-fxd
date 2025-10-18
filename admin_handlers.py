import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from supabase_client import db
from keyboards import Keyboards
from decorators import handle_errors, admin_required, log_user_action
from helpers import truncate_text, format_datetime_arabic

logger = logging.getLogger(__name__)

class AdminHandlers:
    def __init__(self):
        self.broadcast_cache = {}  # Store broadcast messages temporarily
    
    @handle_errors
    @admin_required
    @log_user_action("admin_panel")
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        admin_message = """👑 لوحة تحكم المالك

أهلاً بك في لوحة التحكم الخاصة بالمالك.

اختر العملية التي تريد تنفيذها:"""
        
        await update.message.reply_text(
            admin_message,
            reply_markup=Keyboards.admin_menu()
        )
    
    @handle_errors
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show general statistics"""
        query = update.callback_query
        await query.answer()
        
        stats = await db.get_statistics()
        
        if not stats:
            await query.edit_message_text("❌ حدث خطأ في جلب الإحصائيات.")
            return
        
        stats_message = f"""📊 الإحصائيات العامة

📺 إجمالي القنوات: {stats.get('total_channels', 0)}
⭐️ قنوات VIP: {stats.get('vip_channels', 0)}
🚫 قنوات محظورة: {stats.get('banned_channels', 0)}
📄 إجمالي المنشورات: {stats.get('total_posts', 0)}
⏰ مهام نشطة: {stats.get('active_schedules', 0)}"""
        
        await query.edit_message_text(
            stats_message,
            reply_markup=Keyboards.admin_menu()
        )
    
    @handle_errors
    async def show_all_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show all channels for admin management"""
        query = update.callback_query
        await query.answer()
        
        channels = await db.get_all_channels()
        
        if not channels:
            await query.edit_message_text(
                "📭 لا توجد قنوات مسجلة في النظام.",
                reply_markup=Keyboards.admin_menu()
            )
            return
        
        await query.edit_message_text(
            f"👁️ جميع القنوات ({len(channels)} قناة):\n\nاختر قناة لإدارتها:",
            reply_markup=Keyboards.admin_channels(channels)
        )
    
    @handle_errors
    async def manage_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show channel management options for admin"""
        query = update.callback_query
        await query.answer()
        
        try:
            channel_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        channel = await db.get_channel_by_id(channel_id)
        if not channel:
            await query.answer("❌ لم يتم العثور على القناة.", show_alert=True)
            return
        
        status_text = ""
        if channel['is_banned']:
            status_text += " 🚫 [محظورة]"
        if channel['is_vip']:
            status_text += " ⭐️ [VIP]"
        
        message_text = f"""🛠️ إدارة القناة: {channel['channel_name']}{status_text}

📊 معلومات القناة:
• المعرف: {channel['channel_tg_id']}
• المالك: {channel['user_owner_id']}
• تاريخ الإضافة: {channel['created_at'][:10]}

اختر العملية:"""
        
        await query.edit_message_text(
            message_text,
            reply_markup=Keyboards.admin_channel_actions(
                channel_id, channel['is_banned'], channel['is_vip']
            )
        )
    
    @handle_errors
    async def toggle_channel_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle channel ban status"""
        query = update.callback_query
        await query.answer()
        
        try:
            parts = query.data.split('_')
            channel_id = int(parts[2])
            new_ban_status = parts[3].lower() == 'true'
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        success = await db.update_channel_status(channel_id, is_banned=new_ban_status)
        
        if success:
            status_text = "محظورة" if new_ban_status else "غير محظورة"
            await query.answer(f"✅ تم تحديث حالة القناة إلى: {status_text}")
            
            # Refresh the channel management view
            await self.manage_channel(update, context)
        else:
            await query.answer("❌ حدث خطأ أثناء التحديث.", show_alert=True)
    
    @handle_errors
    async def toggle_channel_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Toggle channel VIP status"""
        query = update.callback_query
        await query.answer()
        
        try:
            parts = query.data.split('_')
            channel_id = int(parts[2])
            new_vip_status = parts[3].lower() == 'true'
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        success = await db.update_channel_status(channel_id, is_vip=new_vip_status)
        
        if success:
            status_text = "VIP" if new_vip_status else "عادية"
            await query.answer(f"✅ تم تحديث حالة القناة إلى: {status_text}")
            
            # Refresh the channel management view
            await self.manage_channel(update, context)
        else:
            await query.answer("❌ حدث خطأ أثناء التحديث.", show_alert=True)
    
    @handle_errors
    async def start_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start broadcast message creation"""
        query = update.callback_query
        await query.answer()
        
        await query.edit_message_text(
            """📣 إرسال رسالة عامة

أرسل الآن الرسالة (نص أو ميديا) التي تريد إرسالها لجميع القنوات.

⚠️ ملاحظة: سيتم إرسال الرسالة لجميع القنوات باستثناء:
• القنوات المحظورة
• قنوات VIP

لإلغاء العملية، أرسل /cancel""",
            reply_markup=Keyboards.cancel_action()
        )
        
        # Set admin state to waiting for broadcast message
        admin_id = update.effective_user.id
        from user_handlers import user_handlers
        user_handlers.user_states[admin_id] = "waiting_broadcast_message"
    
    @handle_errors
    async def handle_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle broadcast message from admin"""
        admin_id = update.effective_user.id
        
        # Store the message for confirmation
        self.broadcast_cache[admin_id] = {
            'message': update.message,
            'text': update.message.text or update.message.caption,
            'has_media': bool(update.message.photo or update.message.video or 
                            update.message.document or update.message.audio)
        }
        
        # Get broadcast channels count
        broadcast_channels = await db.get_broadcast_channels()
        channel_count = len(broadcast_channels)
        
        preview_text = truncate_text(
            self.broadcast_cache[admin_id]['text'] or "[ميديا بدون نص]", 100
        )
        
        confirmation_message = f"""📣 تأكيد الإرسال العام

📄 معاينة الرسالة:
{preview_text}

📊 سيتم الإرسال إلى: {channel_count} قناة

⚠️ هل أنت متأكد من إرسال هذه الرسالة؟"""
        
        await update.message.reply_text(
            confirmation_message,
            reply_markup=Keyboards.broadcast_confirm(preview_text)
        )
    
    @handle_errors
    async def confirm_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and execute broadcast"""
        query = update.callback_query
        await query.answer()
        
        admin_id = update.effective_user.id
        
        if admin_id not in self.broadcast_cache:
            await query.edit_message_text("❌ انتهت صلاحية الرسالة. يرجى البدء من جديد.")
            return
        
        broadcast_data = self.broadcast_cache[admin_id]
        broadcast_channels = await db.get_broadcast_channels()
        
        if not broadcast_channels:
            await query.edit_message_text("📭 لا توجد قنوات مؤهلة للبث.")
            return
        
        # Start broadcasting
        await query.edit_message_text("📡 جاري إرسال الرسالة العامة...")
        
        success_count = 0
        failed_count = 0
        
        for channel in broadcast_channels:
            try:
                if broadcast_data['has_media']:
                    # Forward the original message to preserve media
                    await context.bot.forward_message(
                        chat_id=channel['channel_tg_id'],
                        from_chat_id=broadcast_data['message'].chat_id,
                        message_id=broadcast_data['message'].message_id
                    )
                else:
                    # Send text message
                    await context.bot.send_message(
                        chat_id=channel['channel_tg_id'],
                        text=broadcast_data['text']
                    )
                success_count += 1
                
                # Small delay to avoid rate limiting
                import asyncio
                await asyncio.sleep(0.1)
                
            except TelegramError as e:
                logger.error(f"Failed to broadcast to channel {channel['channel_tg_id']}: {e}")
                failed_count += 1
                
                # If bot was removed, deactivate channel schedules
                if "bot was blocked" in str(e).lower() or "chat not found" in str(e).lower():
                    await db.deactivate_channel_schedules(channel['channel_tg_id'])
        
        # Send result summary
        result_message = f"""✅ تم إنجاز البث العام

📊 النتائج:
• تم الإرسال بنجاح: {success_count} قناة
• فشل الإرسال: {failed_count} قناة
• إجمالي القنوات: {success_count + failed_count}"""
        
        await query.edit_message_text(
            result_message,
            reply_markup=Keyboards.admin_menu()
        )
        
        # Clear cache
        self.broadcast_cache.pop(admin_id, None)
        from user_handlers import user_handlers
        user_handlers.user_states.pop(admin_id, None)
        
        logger.info(f"Broadcast completed by admin {admin_id}: {success_count} success, {failed_count} failed")
    
    @handle_errors
    async def cancel_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel broadcast operation"""
        query = update.callback_query
        await query.answer()
        
        admin_id = update.effective_user.id
        self.broadcast_cache.pop(admin_id, None)
        from user_handlers import user_handlers
        user_handlers.user_states.pop(admin_id, None)
        
        await query.edit_message_text(
            "❌ تم إلغاء البث العام.",
            reply_markup=Keyboards.admin_menu()
        )
    
    @handle_errors
    async def show_channel_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show posts for a specific channel (admin view)"""
        query = update.callback_query
        await query.answer()
        
        try:
            channel_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        # Get channel info
        channel = await db.get_channel_by_id(channel_id)
        if not channel:
            await query.answer("❌ لم يتم العثور على القناة.", show_alert=True)
            return
        
        # Get all posts for this channel (from all users)
        # Note: This requires a modification to the database query
        # For now, we'll show a placeholder message
        
        await query.edit_message_text(
            f"""📄 منشورات القناة: {channel['channel_name']}

⚠️ عرض منشورات القناة من لوحة الإدارة قيد التطوير.

يمكنك العودة لإدارة القناة أو اختيار قناة أخرى.""",
            reply_markup=Keyboards.admin_channels([channel])
        )

# Global instance
admin_handlers = AdminHandlers()