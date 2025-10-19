import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError

# Import modules after basic imports to avoid circular imports
logger = logging.getLogger(__name__)

class UserHandlers:
    def __init__(self):
        self.user_states = {}  # Store user conversation states
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - simplified without decorators for now"""
        try:
            user_id = update.effective_user.id
            user_name = update.effective_user.first_name or "المستخدم"
            
            logger.info(f"User {user_id} started the bot")
            
            welcome_message = f"""👋 أهلاً بك {user_name} في بوت مدير القنوات!

استخدم هذا البوت لجدولة منشوراتك تلقائياً في قنواتك.

للبدء، يجب أن ترفع البوت كـ "مشرف" (Admin) في قناتك مع صلاحية إرسال الرسائل.

اختر من القائمة أدناه:"""
            
            # Import keyboards locally to avoid circular imports
            from keyboards import Keyboards
            
            await update.message.reply_text(
                welcome_message,
                reply_markup=Keyboards.main_menu()
            )
            
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text(
                "❌ حدث خطأ في تشغيل البوت. يرجى المحاولة مرة أخرى أو التواصل مع المطور."
            )
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages based on user state"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            logger.info(f"Text message from user {user_id}: {message_text}")
            
            # Import keyboards locally
            from keyboards import Keyboards
            
            # Check for main menu buttons
            if message_text == "➕ إضافة قناة جديدة":
                await self.add_channel_start(update, context)
            elif message_text == "📁 قنواتي ومنشوراتي":
                await self.show_my_channels(update, context)
            elif message_text == "❌ إلغاء":
                await self.cancel_current_action(update, context)
            else:
                # Handle state-based messages
                await self.handle_state_message(update, context)
                
        except Exception as e:
            logger.error(f"Error in handle_text_message: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة الرسالة.")
    
    async def add_channel_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start the process of adding a new channel"""
        try:
            from keyboards import Keyboards
            
            instructions = """📝 لإضافة قناة جديدة، اتبع الخطوات التالية:

1️⃣ قم بإضافة البوت كـ "مشرف" في قناتك
2️⃣ تأكد من إعطاء البوت صلاحية "إرسال الرسائل"
3️⃣ بعد ذلك، قم بإعادة توجيه (Forward) أي رسالة من تلك القناة إلى هنا

⚠️ تأكد من أن البوت مشرف في القناة وله الصلاحيات المطلوبة قبل إعادة التوجيه."""
            
            self.user_states[update.effective_user.id] = "waiting_channel_forward"
            
            await update.message.reply_text(
                instructions,
                reply_markup=Keyboards.cancel_action()
            )
            
        except Exception as e:
            logger.error(f"Error in add_channel_start: {e}")
            await update.message.reply_text("❌ حدث خطأ. يرجى المحاولة مرة أخرى.")
    
    async def show_my_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's channels"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            
            user_id = update.effective_user.id
            channels = await db.get_user_channels(user_id)
            
            if not channels:
                await update.message.reply_text(
                    "📭 ليس لديك أي قنوات مضافة.\n\nاضغط 'إضافة قناة جديدة' للبدء.",
                    reply_markup=Keyboards.main_menu()
                )
                return
            
            await update.message.reply_text(
                "📁 قنواتك المضافة:\n\nاختر القناة التي تريد إدارتها:",
                reply_markup=Keyboards.user_channels(channels)
            )
            
        except Exception as e:
            logger.error(f"Error in show_my_channels: {e}")
            await update.message.reply_text("❌ حدث خطأ في جلب القنوات.")
    
    async def handle_forwarded_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forwarded messages to add channels"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            from helpers import sanitize_channel_name
            
            user_id = update.effective_user.id
            
            if self.user_states.get(user_id) != "waiting_channel_forward":
                return
            
            if not update.message.forward_from_chat:
                await update.message.reply_text("❌ يجب إعادة توجيه رسالة من القناة التي تريد إضافتها.")
                return
            
            chat = update.message.forward_from_chat
            
            # Check if it's a channel
            if chat.type not in ['channel', 'supergroup']:
                await update.message.reply_text("❌ يمكن إضافة القنوات والمجموعات العامة فقط.")
                return
            
            channel_tg_id = chat.id
            channel_name = sanitize_channel_name(chat.title or "قناة غير محددة")
            
            # Check if channel already exists
            existing_channel = await db.get_channel_by_tg_id(channel_tg_id)
            if existing_channel:
                await update.message.reply_text(f"❌ القناة '{channel_name}' مضافة مسبقاً للبوت.")
                self.user_states.pop(user_id, None)
                return
            
            # Verify bot is admin in the channel
            try:
                bot_member = await context.bot.get_chat_member(channel_tg_id, context.bot.id)
                if bot_member.status not in ['administrator']:
                    await update.message.reply_text(
                        f"❌ فشل التحقق. يرجى التأكد من أن البوت مشرف في القناة '{channel_name}' ولديه صلاحية إرسال الرسائل."
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                # Check if bot can send messages
                if not bot_member.can_post_messages and chat.type == 'channel':
                    await update.message.reply_text(
                        f"❌ البوت لا يملك صلاحية إرسال الرسائل في القناة '{channel_name}'. يرجى إعطاء البوت هذه الصلاحية."
                    )
                    self.user_states.pop(user_id, None)
                    return
                    
            except TelegramError as e:
                await update.message.reply_text(
                    f"❌ فشل التحقق من القناة '{channel_name}'. تأكد من أن البوت مشرف فيها.\n\nخطأ: {str(e)}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Add channel to database
            success = await db.add_channel(channel_tg_id, channel_name, user_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ تم ربط قناة '{channel_name}' بنجاح!\n\nيمكنك الآن إدارة منشوراتها من 'قنواتي ومنشوراتي'.",
                    reply_markup=Keyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء إضافة القناة. يرجى المحاولة لاحقاً.",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_forwarded_message: {e}")
            await update.message.reply_text("❌ حدث خطأ في إضافة القناة.")
    
    async def handle_state_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages based on user state"""
        try:
            user_id = update.effective_user.id
            state = self.user_states.get(user_id)
            
            if not state:
                # Handle forwarded messages for channel addition
                if update.message.forward_from_chat:
                    await self.handle_forwarded_message(update, context)
                return
            
            if state == "waiting_channel_forward":
                if update.message.forward_from_chat:
                    await self.handle_forwarded_message(update, context)
                else:
                    await update.message.reply_text("❌ يجب إعادة توجيه رسالة من القناة.")
            
            elif state.startswith("creating_post_"):
                await self.handle_post_creation(update, context, state)
            
            elif state.startswith("editing_post_"):
                await self.handle_post_editing(update, context, state)
            
            elif state.startswith("scheduling_"):
                await self.handle_scheduling_input(update, context, state)
                
        except Exception as e:
            logger.error(f"Error in handle_state_message: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة الحالة.")
    
    async def handle_post_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle post creation process"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            from helpers import is_media_message
            
            user_id = update.effective_user.id
            channel_id = int(state.split("_")[-1])
            
            # Get message content
            post_content = update.message.text or update.message.caption
            media_file_id = None
            media_type = None
            
            # Check for media
            has_media, media_type, media_file_id = is_media_message(update.message)
            
            if not post_content and not has_media:
                await update.message.reply_text("❌ يجب أن يحتوي المنشور على نص أو ميديا على الأقل.")
                return
            
            # Save post to database
            post_id = await db.add_post(user_id, channel_id, post_content, media_file_id, media_type)
            
            if post_id:
                await update.message.reply_text(
                    "✅ تم حفظ المنشور بنجاح!\n\nيمكنك الآن جدولته من 'إعدادات الجدولة'.",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء حفظ المنشور. يرجى المحاولة لاحقاً.",
                    reply_markup=Keyboards.back_to_main()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_post_creation: {e}")
            await update.message.reply_text("❌ حدث خطأ في إنشاء المنشور.")
    
    async def handle_post_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle post editing process"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            from helpers import is_media_message
            
            user_id = update.effective_user.id
            post_id = int(state.split("_")[-1])
            
            # Get new content
            new_content = update.message.text or update.message.caption
            new_media_file_id = None
            new_media_type = None
            
            # Check for media
            has_media, new_media_type, new_media_file_id = is_media_message(update.message)
            
            if not new_content and not has_media:
                await update.message.reply_text("❌ يجب أن يحتوي المنشور على نص أو ميديا على الأقل.")
                return
            
            # Update post
            success = await db.update_post(post_id, user_id, new_content, new_media_file_id, new_media_type)
            
            if success:
                await update.message.reply_text(
                    "✅ تم تحديث المنشور بنجاح!",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء تحديث المنشور.",
                    reply_markup=Keyboards.back_to_main()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_post_editing: {e}")
            await update.message.reply_text("❌ حدث خطأ في تعديل المنشور.")
    
    async def handle_scheduling_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle scheduling time input"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            # Parse state to get scheduling info
            parts = state.split("_")
            if len(parts) < 4:
                return
            
            schedule_type = parts[1]  # e.g., "daily", "weekly", "once", "custom"
            post_id = int(parts[2])
            
            # Handle different scheduling inputs based on type
            if schedule_type in ["daily", "2days"]:
                await self.handle_time_input(update, context, post_id, schedule_type, message_text)
            elif schedule_type == "weekly":
                if len(parts) == 4:  # waiting for weekday selection
                    # This should be handled in callback handlers
                    pass
                else:  # waiting for time input after weekday selection
                    weekday = int(parts[4])
                    await self.handle_time_input(update, context, post_id, schedule_type, message_text, weekday)
            elif schedule_type == "once":
                await self.handle_once_scheduling(update, context, post_id, message_text)
            elif schedule_type == "custom":
                await self.handle_custom_cron(update, context, post_id, message_text)
                
        except Exception as e:
            logger.error(f"Error in handle_scheduling_input: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة الجدولة.")
    
    async def handle_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               post_id: int, schedule_type: str, time_text: str, weekday: int = None):
        """Handle time input for scheduling"""
        try:
            from helpers import parse_time_string, create_cron_expression, get_next_occurrence
            from keyboards import Keyboards
            from supabase_client import db
            
            user_id = update.effective_user.id
            
            # Parse time
            time_obj = parse_time_string(time_text)
            if not time_obj:
                await update.message.reply_text(
                    "❌ صيغة الوقت غير صحيحة. يرجى استخدام صيغة HH:MM مثل 14:30",
                    reply_markup=Keyboards.time_input_help()
                )
                return
            
            # Create cron expression
            cron_expr = create_cron_expression(schedule_type, time_obj, weekday)
            if not cron_expr:
                await update.message.reply_text("❌ حدث خطأ في إنشاء الجدولة.")
                self.user_states.pop(user_id, None)
                return
            
            # Get next run time
            next_run = get_next_occurrence(cron_expr)
            if not next_run:
                await update.message.reply_text("❌ حدث خطأ في حساب الوقت القادم.")
                self.user_states.pop(user_id, None)
                return
            
            # Get post and channel info
            post = await db.get_post_by_id(post_id)
            if not post:
                await update.message.reply_text("❌ لم يتم العثور على المنشور.")
                self.user_states.pop(user_id, None)
                return
            
            channel = await db.get_channel_by_id(post['channel_id'])
            if not channel:
                await update.message.reply_text("❌ لم يتم العثور على القناة.")
                self.user_states.pop(user_id, None)
                return
            
            # Save schedule
            schedule_id = await db.add_schedule(
                post_id, channel['channel_tg_id'], user_id, cron_expr, next_run
            )
            
            if schedule_id:
                from helpers import format_datetime_arabic
                next_run_formatted = format_datetime_arabic(next_run)
                
                await update.message.reply_text(
                    f"✅ تمت جدولة المنشور بنجاح!\n\n"
                    f"📺 القناة: {channel['channel_name']}\n"
                    f"⏰ الموعد القادم: {next_run_formatted}",
                    reply_markup=Keyboards.main_menu()
                )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء حفظ الجدولة.",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_time_input: {e}")
            await update.message.reply_text("❌ حدث خطأ في معالجة الوقت.")
    
    async def handle_once_scheduling(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post_id: int, datetime_text: str):
        """Handle one-time scheduling"""
        from keyboards import Keyboards
        
        await update.message.reply_text(
            "⚠️ الجدولة لمرة واحدة تحتاج تطوير إضافي.\nيرجى استخدام الجدولة اليومية أو الأسبوعية حالياً.",
            reply_markup=Keyboards.main_menu()
        )
        self.user_states.pop(update.effective_user.id, None)
    
    async def handle_custom_cron(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               post_id: int, cron_text: str):
        """Handle custom cron expression"""
        try:
            from helpers import validate_cron_expression, get_next_occurrence, format_datetime_arabic
            from keyboards import Keyboards
            from supabase_client import db
            
            user_id = update.effective_user.id
            
            if not validate_cron_expression(cron_text):
                await update.message.reply_text(
                    "❌ صيغة Cron غير صحيحة.\n\n"
                    "أمثلة صحيحة:\n"
                    "• `0 9 * * *` - يومياً في 9:00\n"
                    "• `30 14 * * 1` - كل إثنين في 14:30\n"
                    "• `0 */6 * * *` - كل 6 ساعات"
                )
                return
            
            # Get next run time
            next_run = get_next_occurrence(cron_text)
            if not next_run:
                await update.message.reply_text("❌ حدث خطأ في حساب الوقت القادم.")
                self.user_states.pop(user_id, None)
                return
            
            # Get post and channel info
            post = await db.get_post_by_id(post_id)
            channel = await db.get_channel_by_id(post['channel_id'])
            
            # Save schedule
            schedule_id = await db.add_schedule(
                post_id, channel['channel_tg_id'], user_id, cron_text, next_run
            )
            
            if schedule_id:
                next_run_formatted = format_datetime_arabic(next_run)
                
                await update.message.reply_text(
                    f"✅ تمت جدولة المنشور بنجاح!\n\n"
                    f"📺 القناة: {channel['channel_name']}\n"
                    f"🔧 Cron: `{cron_text}`\n"
                    f"⏰ الموعد القادم: {next_run_formatted}",
                    reply_markup=Keyboards.main_menu(),
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(
                    "❌ حدث خطأ أثناء حفظ الجدولة.",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_custom_cron: {e}")
            await update.message.reply_text("❌ حدث خطأ في الجدولة المخصصة.")
    
    async def cancel_current_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current user action"""
        try:
            from keyboards import Keyboards
            
            user_id = update.effective_user.id
            self.user_states.pop(user_id, None)
            
            await update.message.reply_text(
                "❌ تم إلغاء العملية الحالية.",
                reply_markup=Keyboards.main_menu()
            )
            
        except Exception as e:
            logger.error(f"Error in cancel_current_action: {e}")
            await update.message.reply_text("❌ حدث خطأ في الإلغاء.")

# Global instance
user_handlers = UserHandlers()