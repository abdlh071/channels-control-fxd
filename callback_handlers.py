import logging
from telegram import Update
from telegram.ext import ContextTypes
from supabase_client import db
from keyboards import Keyboards
from decorators import handle_errors
from helpers import truncate_text

logger = logging.getLogger(__name__)

class CallbackHandlers:
    @handle_errors
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main callback handler router"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        # Route to appropriate handler based on callback data
        if data == "main_menu":
            await self.show_main_menu(update, context)
        elif data == "my_channels":
            await self.show_user_channels(update, context)
        elif data.startswith("channel_"):
            await self.show_channel_management(update, context)
        elif data.startswith("posts_"):
            await self.show_channel_posts(update, context)
        elif data.startswith("new_post_"):
            await self.start_post_creation(update, context)
        elif data.startswith("post_"):
            await self.show_post_actions(update, context)
        elif data.startswith("edit_post_"):
            await self.start_post_editing(update, context)
        elif data.startswith("delete_post_"):
            await self.confirm_post_deletion(update, context)
        elif data.startswith("confirm_delete_"):
            await self.execute_deletion(update, context)
        elif data.startswith("cancel_delete_"):
            await self.cancel_deletion(update, context)
        elif data.startswith("schedule_post_"):
            await self.show_scheduling_options(update, context)
        elif data.startswith("sched_"):
            await self.handle_scheduling_choice(update, context)
        elif data.startswith("weekday_"):
            await self.handle_weekday_selection(update, context)
        elif data.startswith("delete_channel_"):
            await self.confirm_channel_deletion(update, context)
        elif data == "cancel_action":
            await self.cancel_current_action(update, context)
        
        # Admin callbacks
        elif data == "admin_menu":
            from admin_handlers import admin_handlers
            await admin_handlers.admin_command(update, context)
        elif data == "admin_stats":
            from admin_handlers import admin_handlers
            await admin_handlers.show_statistics(update, context)
        elif data == "admin_channels":
            from admin_handlers import admin_handlers
            await admin_handlers.show_all_channels(update, context)
        elif data.startswith("admin_channel_"):
            from admin_handlers import admin_handlers
            await admin_handlers.manage_channel(update, context)
        elif data.startswith("admin_ban_"):
            from admin_handlers import admin_handlers
            await admin_handlers.toggle_channel_ban(update, context)
        elif data.startswith("admin_vip_"):
            from admin_handlers import admin_handlers
            await admin_handlers.toggle_channel_vip(update, context)
        elif data.startswith("admin_posts_"):
            from admin_handlers import admin_handlers
            await admin_handlers.show_channel_posts(update, context)
        elif data == "admin_broadcast":
            from admin_handlers import admin_handlers
            await admin_handlers.start_broadcast(update, context)
        elif data == "confirm_broadcast":
            from admin_handlers import admin_handlers
            await admin_handlers.confirm_broadcast(update, context)
        elif data == "cancel_broadcast":
            from admin_handlers import admin_handlers
            await admin_handlers.cancel_broadcast(update, context)
    
    @handle_errors
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu"""
        query = update.callback_query
        
        await query.edit_message_text(
            "🏠 القائمة الرئيسية\n\nاختر العملية التي تريد تنفيذها:",
            reply_markup=Keyboards.main_menu()
        )
    
    @handle_errors
    async def show_user_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's channels"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        channels = await db.get_user_channels(user_id)
        
        if not channels:
            await query.edit_message_text(
                "📭 ليس لديك أي قنوات مضافة.\n\nاستخدم القائمة الرئيسية لإضافة قناة جديدة.",
                reply_markup=Keyboards.back_to_main()
            )
            return
        
        await query.edit_message_text(
            "📁 قنواتك المضافة:\n\nاختر القناة التي تريد إدارتها:",
            reply_markup=Keyboards.user_channels(channels)
        )
    
    @handle_errors
    async def show_channel_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show channel management options"""
        query = update.callback_query
        
        try:
            channel_id = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        # Verify user owns this channel
        channel = await db.get_channel_by_id(channel_id)
        if not channel or channel['user_owner_id'] != update.effective_user.id:
            await query.answer("❌ ليس لديك صلاحية للوصول إلى هذه القناة.", show_alert=True)
            return
        
        await query.edit_message_text(
            f"⚙️ إدارة القناة: {channel['channel_name']}\n\nاختر العملية التي تريد تنفيذها:",
            reply_markup=Keyboards.channel_management(channel_id)
        )
    
    @handle_errors
    async def show_channel_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show posts for a channel"""
        query = update.callback_query
        
        try:
            channel_id = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        user_id = update.effective_user.id
        posts = await db.get_channel_posts(channel_id, user_id)
        
        if not posts:
            channel = await db.get_channel_by_id(channel_id)
            await query.edit_message_text(
                f"📄 منشورات القناة: {channel['channel_name']}\n\n📭 لا توجد منشورات محفوظة.",
                reply_markup=Keyboards.channel_posts([], channel_id)
            )
            return
        
        channel = await db.get_channel_by_id(channel_id)
        await query.edit_message_text(
            f"📄 منشورات القناة: {channel['channel_name']}\n\nاختر منشوراً لإدارته:",
            reply_markup=Keyboards.channel_posts(posts, channel_id)
        )
    
    @handle_errors
    async def start_post_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start post creation process"""
        query = update.callback_query
        
        try:
            channel_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        # Verify user owns this channel
        channel = await db.get_channel_by_id(channel_id)
        if not channel or channel['user_owner_id'] != update.effective_user.id:
            await query.answer("❌ ليس لديك صلاحية للوصول إلى هذه القناة.", show_alert=True)
            return
        
        await query.edit_message_text(
            f"➕ إنشاء منشور جديد للقناة: {channel['channel_name']}\n\n"
            "أرسل الآن محتوى المنشور الذي تريد حفظه:\n"
            "• نص\n"
            "• صورة مع نص اختياري\n"
            "• فيديو مع نص اختياري\n"
            "• ملف مع نص اختياري\n\n"
            "لإلغاء العملية، اضغط الزر أدناه.",
            reply_markup=Keyboards.cancel_action()
        )
        
        # Set user state
        from user_handlers import user_handlers
        user_handlers.user_states[update.effective_user.id] = f"creating_post_{channel_id}"
    
    @handle_errors
    async def show_post_actions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show actions for a specific post"""
        query = update.callback_query
        
        try:
            post_id = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        post = await db.get_post_by_id(post_id)
        if not post or post['user_id'] != update.effective_user.id:
            await query.answer("❌ لم يتم العثور على المنشور.", show_alert=True)
            return
        
        # Get channel info
        channel = await db.get_channel_by_id(post['channel_id'])
        
        # Create post preview
        content_preview = ""
        if post['post_content']:
            content_preview = truncate_text(post['post_content'], 100)
        else:
            content_preview = f"[{post['media_type']}]" if post['media_type'] else "[منشور فارغ]"
        
        await query.edit_message_text(
            f"📄 إدارة المنشور\n\n"
            f"📺 القناة: {channel['channel_name']}\n"
            f"📄 المحتوى: {content_preview}\n\n"
            "اختر العملية:",
            reply_markup=Keyboards.post_actions(post_id, post['channel_id'])
        )
    
    @handle_errors
    async def start_post_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start post editing process"""
        query = update.callback_query
        
        try:
            post_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        post = await db.get_post_by_id(post_id)
        if not post or post['user_id'] != update.effective_user.id:
            await query.answer("❌ لم يتم العثور على المنشور.", show_alert=True)
            return
        
        await query.edit_message_text(
            "✏️ تعديل المنشور\n\n"
            "أرسل المحتوى الجديد للمنشور (نص و/أو ميديا).\n\n"
            "لإلغاء العملية، اضغط الزر أدناه.",
            reply_markup=Keyboards.cancel_action()
        )
        
        # Set user state
        from user_handlers import user_handlers
        user_handlers.user_states[update.effective_user.id] = f"editing_post_{post_id}"
    
    @handle_errors
    async def confirm_post_deletion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm post deletion"""
        query = update.callback_query
        
        try:
            post_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        post = await db.get_post_by_id(post_id)
        if not post or post['user_id'] != update.effective_user.id:
            await query.answer("❌ لم يتم العثور على المنشور.", show_alert=True)
            return
        
        content_preview = truncate_text(post['post_content'] or "[ميديا]", 50)
        
        await query.edit_message_text(
            f"🗑️ حذف المنشور\n\n"
            f"📄 المحتوى: {content_preview}\n\n"
            "⚠️ هل أنت متأكد من حذف هذا المنشور؟\n"
            "سيتم حذف جميع الجداول المرتبطة به أيضاً.",
            reply_markup=Keyboards.confirm_delete("post", post_id)
        )
    
    @handle_errors
    async def confirm_channel_deletion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm channel deletion"""
        query = update.callback_query
        
        try:
            channel_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        channel = await db.get_channel_by_id(channel_id)
        if not channel or channel['user_owner_id'] != update.effective_user.id:
            await query.answer("❌ ليس لديك صلاحية لحذف هذه القناة.", show_alert=True)
            return
        
        await query.edit_message_text(
            f"🗑️ حذف القناة\n\n"
            f"📺 القناة: {channel['channel_name']}\n\n"
            "⚠️ هل أنت متأكد من حذف هذه القناة؟\n"
            "سيتم حذف جميع المنشورات والجداول المرتبطة بها.",
            reply_markup=Keyboards.confirm_delete("channel", channel_id)
        )
    
    @handle_errors
    async def execute_deletion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute confirmed deletion"""
        query = update.callback_query
        
        try:
            parts = query.data.split('_')
            item_type = parts[2]
            item_id = int(parts[3])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        user_id = update.effective_user.id
        
        if item_type == "post":
            success = await db.delete_post(item_id, user_id)
            if success:
                await query.edit_message_text(
                    "✅ تم حذف المنشور بنجاح.",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await query.edit_message_text(
                    "❌ حدث خطأ أثناء حذف المنشور.",
                    reply_markup=Keyboards.back_to_main()
                )
        
        elif item_type == "channel":
            success = await db.delete_channel(item_id, user_id)
            if success:
                await query.edit_message_text(
                    "✅ تم حذف القناة بنجاح من البوت.\n\n"
                    "ملاحظة: البوت لا يزال مشرفاً في القناة. يمكنك إزالته يدوياً إذا أردت.",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await query.edit_message_text(
                    "❌ حدث خطأ أثناء حذف القناة.",
                    reply_markup=Keyboards.back_to_main()
                )
    
    @handle_errors
    async def cancel_deletion(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel deletion operation"""
        query = update.callback_query
        
        await query.edit_message_text(
            "❌ تم إلغاء عملية الحذف.",
            reply_markup=Keyboards.back_to_main()
        )
    
    @handle_errors
    async def show_scheduling_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show scheduling options for a post"""
        query = update.callback_query
        
        try:
            post_id = int(query.data.split('_')[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        post = await db.get_post_by_id(post_id)
        if not post or post['user_id'] != update.effective_user.id:
            await query.answer("❌ لم يتم العثور على المنشور.", show_alert=True)
            return
        
        await query.edit_message_text(
            "⏰ جدولة المنشور\n\n"
            "اختر نوع الجدولة:",
            reply_markup=Keyboards.schedule_options(post_id)
        )
    
    @handle_errors
    async def handle_scheduling_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle scheduling type choice"""
        query = update.callback_query
        
        try:
            parts = query.data.split('_')
            schedule_type = parts[1]
            post_id = int(parts[2])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        from user_handlers import user_handlers
        user_id = update.effective_user.id
        
        if schedule_type == "daily":
            await query.edit_message_text(
                "📅 جدولة يومية\n\n"
                "أدخل الوقت الذي تريد النشر فيه يومياً:\n"
                "(مثال: 14:30)",
                reply_markup=Keyboards.time_input_help()
            )
            user_handlers.user_states[user_id] = f"scheduling_daily_{post_id}"
        
        elif schedule_type == "2days":
            await query.edit_message_text(
                "📅 جدولة كل يومين\n\n"
                "أدخل الوقت الذي تريد النشر فيه كل يومين:\n"
                "(مثال: 18:00)",
                reply_markup=Keyboards.time_input_help()
            )
            user_handlers.user_states[user_id] = f"scheduling_2days_{post_id}"
        
        elif schedule_type == "weekly":
            await query.edit_message_text(
                "📅 جدولة أسبوعية\n\n"
                "اختر اليوم الذي تريد النشر فيه:",
                reply_markup=Keyboards.weekday_selection()
            )
            user_handlers.user_states[user_id] = f"scheduling_weekly_{post_id}"
        
        elif schedule_type == "once":
            await query.edit_message_text(
                "📅 جدولة لمرة واحدة\n\n"
                "⚠️ هذه الميزة قيد التطوير.\n"
                "يرجى استخدام الجدولة اليومية أو الأسبوعية حالياً.",
                reply_markup=Keyboards.schedule_options(post_id)
            )
        
        elif schedule_type == "custom":
            await query.edit_message_text(
                "⚙️ جدولة مخصصة (Cron)\n\n"
                "أدخل تعبير Cron للجدولة:\n\n"
                "أمثلة:\n"
                "• `0 9 * * *` - يومياً في 9:00\n"
                "• `30 14 * * 1` - كل إثنين في 14:30\n"
                "• `0 */6 * * *` - كل 6 ساعات",
                reply_markup=Keyboards.cancel_action(),
                parse_mode='Markdown'
            )
            user_handlers.user_states[user_id] = f"scheduling_custom_{post_id}"
    
    @handle_errors
    async def handle_weekday_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle weekday selection for weekly scheduling"""
        query = update.callback_query
        
        try:
            weekday = int(query.data.split('_')[1])
        except (IndexError, ValueError):
            await query.answer("❌ خطأ في البيانات.", show_alert=True)
            return
        
        from user_handlers import user_handlers
        user_id = update.effective_user.id
        current_state = user_handlers.user_states.get(user_id, "")
        
        if not current_state.startswith("scheduling_weekly_"):
            await query.answer("❌ خطأ في الحالة.", show_alert=True)
            return
        
        post_id = current_state.split('_')[2]
        
        from helpers import get_weekday_name
        weekday_name = get_weekday_name(weekday)
        
        await query.edit_message_text(
            f"📅 جدولة أسبوعية - {weekday_name}\n\n"
            f"أدخل الوقت الذي تريد النشر فيه كل {weekday_name}:\n"
            "(مثال: 12:00)",
            reply_markup=Keyboards.time_input_help()
        )
        
        user_handlers.user_states[user_id] = f"scheduling_weekly_{post_id}_{weekday}"
    
    @handle_errors
    async def cancel_current_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current action"""
        query = update.callback_query
        
        from user_handlers import user_handlers
        user_handlers.user_states.pop(update.effective_user.id, None)
        
        await query.edit_message_text(
            "❌ تم إلغاء العملية الحالية.",
            reply_markup=Keyboards.back_to_main()
        )

# Global instance
callback_handlers = CallbackHandlers()