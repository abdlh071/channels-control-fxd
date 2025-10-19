import logging
from telegram import Update, Message
from telegram.ext import ContextTypes
from telegram.error import TelegramError, BadRequest, Forbidden

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
            logger.error(f"Error in start_command: {e}", exc_info=True)
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
            logger.error(f"Error in handle_text_message for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(f"❌ حدث خطأ في معالجة الرسالة: {str(e)[:100]}")
    
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
            logger.error(f"Error in add_channel_start for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(f"❌ حدث خطأ في بدء إضافة القناة: {str(e)[:100]}")
    
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
            logger.error(f"Error in show_my_channels for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(f"❌ حدث خطأ في جلب القنوات: {str(e)[:100]}")
    
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
            
            logger.info(f"User {user_id} attempting to add channel {channel_name} (ID: {channel_tg_id})")
            
            # Check if channel already exists
            existing_channel = await db.get_channel_by_tg_id(channel_tg_id)
            if existing_channel:
                await update.message.reply_text(f"❌ القناة '{channel_name}' مضافة مسبقاً للبوت.")
                self.user_states.pop(user_id, None)
                return
            
            # Verify bot is admin in the channel
            try:
                bot_member = await context.bot.get_chat_member(channel_tg_id, context.bot.id)
                logger.info(f"Bot status in channel {channel_name}: {bot_member.status}")
                
                if bot_member.status not in ['administrator']:
                    await update.message.reply_text(
                        f"❌ فشل التحقق. البوت ليس مشرف في القناة '{channel_name}'.\n\n"
                        f"الحالة الحالية للبوت: {bot_member.status}\n\n"
                        "يرجى:\n"
                        "1. إضافة البوت كمشرف في القناة\n"
                        "2. إعطاء البوت صلاحية 'إرسال الرسائل'\n"
                        "3. إعادة المحاولة"
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                # Check if bot can send messages (for channels)
                if chat.type == 'channel' and not bot_member.can_post_messages:
                    await update.message.reply_text(
                        f"❌ البوت لا يملك صلاحية إرسال الرسائل في القناة '{channel_name}'.\n\n"
                        "يرجى إعطاء البوت صلاحية 'إرسال الرسائل' من إعدادات المشرفين."
                    )
                    self.user_states.pop(user_id, None)
                    return
                    
            except Forbidden:
                await update.message.reply_text(
                    f"❌ البوت محظور أو غير موجود في القناة '{channel_name}'.\n\n"
                    "يرجى:\n"
                    "1. التأكد من إضافة البوت إلى القناة\n"
                    "2. رفعه كمشرف مع الصلاحيات المناسبة\n"
                    "3. إعادة المحاولة"
                )
                self.user_states.pop(user_id, None)
                return
            except BadRequest as e:
                await update.message.reply_text(
                    f"❌ خطأ في الوصول للقناة '{channel_name}'.\n\n"
                    f"تفاصيل الخطأ: {str(e)}\n\n"
                    "يرجى التأكد من أن القناة عامة أو أن البوت مضاف إليها."
                )
                self.user_states.pop(user_id, None)
                return
            except TelegramError as e:
                await update.message.reply_text(
                    f"❌ فشل التحقق من القناة '{channel_name}'.\n\n"
                    f"رمز الخطأ: {type(e).__name__}\n"
                    f"رسالة الخطأ: {str(e)}\n\n"
                    "يرجى التأكد من أن البوت مشرف في القناة وإعادة المحاولة."
                )
                self.user_states.pop(user_id, None)
                return
            
            # Add channel to database
            try:
                success = await db.add_channel(channel_tg_id, channel_name, user_id)
                
                if success:
                    logger.info(f"Successfully added channel {channel_name} for user {user_id}")
                    await update.message.reply_text(
                        f"✅ تم ربط قناة '{channel_name}' بنجاح!\n\nيمكنك الآن إدارة منشوراتها من 'قنواتي ومنشوراتي'.",
                        reply_markup=Keyboards.main_menu()
                    )
                else:
                    logger.error(f"Failed to add channel {channel_name} to database for user {user_id}")
                    await update.message.reply_text(
                        f"❌ حدث خطأ في قاعدة البيانات أثناء إضافة القناة '{channel_name}'.\n\n"
                        "يرجى المحاولة لاحقاً أو التواصل مع المطور.",
                        reply_markup=Keyboards.main_menu()
                    )
                
            except Exception as db_error:
                logger.error(f"Database error when adding channel for user {user_id}: {db_error}", exc_info=True)
                await update.message.reply_text(
                    f"❌ خطأ في قاعدة البيانات: {str(db_error)[:100]}\n\n"
                    "يرجى المحاولة لاحقاً.",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_forwarded_message for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ عام في إضافة القناة: {str(e)[:100]}\n\n"
                "يرجى المحاولة لاحقاً أو التواصل مع المطور."
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_state_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages based on user state"""
        try:
            user_id = update.effective_user.id
            state = self.user_states.get(user_id)
            
            logger.info(f"Handling state message for user {user_id}, state: {state}")
            
            if not state:
                # Handle forwarded messages for channel addition
                if update.message.forward_from_chat:
                    await self.handle_forwarded_message(update, context)
                return
            
            if state == "waiting_channel_forward":
                if update.message.forward_from_chat:
                    await self.handle_forwarded_message(update, context)
                else:
                    await update.message.reply_text(
                        "❌ يجب إعادة توجيه رسالة من القناة.\n\n"
                        "للإلغاء، اضغط زر 'إلغاء' أو اكتب /start"
                    )
            
            elif state.startswith("creating_post_"):
                await self.handle_post_creation(update, context, state)
            
            elif state.startswith("editing_post_"):
                await self.handle_post_editing(update, context, state)
            
            elif state.startswith("scheduling_"):
                await self.handle_scheduling_input(update, context, state)
            
            else:
                logger.warning(f"Unknown state for user {user_id}: {state}")
                await update.message.reply_text(
                    f"❌ حالة غير معروفة: {state}\n\n"
                    "سيتم إعادة تعيين حالتك. اضغط /start للبدء من جديد."
                )
                self.user_states.pop(user_id, None)
                
        except Exception as e:
            logger.error(f"Error in handle_state_message for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في معالجة الحالة: {str(e)[:100]}\n\n"
                "سيتم إعادة تعيين حالتك. اضغط /start للبدء من جديد."
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_post_creation(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle post creation process"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            from helpers import is_media_message
            
            user_id = update.effective_user.id
            
            try:
                channel_id = int(state.split("_")[-1])
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid state format for post creation: {state}")
                await update.message.reply_text(
                    "❌ خطأ في معرف القناة. سيتم إعادة تعيين الحالة.",
                    reply_markup=Keyboards.main_menu()
                )
                self.user_states.pop(user_id, None)
                return
            
            # Get message content
            post_content = update.message.text or update.message.caption
            media_file_id = None
            media_type = None
            
            # Check for media
            has_media, media_type, media_file_id = is_media_message(update.message)
            
            if not post_content and not has_media:
                await update.message.reply_text(
                    "❌ يجب أن يحتوي المنشور على نص أو ميديا على الأقل.\n\n"
                    "أرسل المحتوى مرة أخرى أو اضغط 'إلغاء'."
                )
                return
            
            logger.info(f"Creating post for user {user_id}, channel {channel_id}, content length: {len(post_content or '')}, media: {media_type}")
            
            # Save post to database
            post_id = await db.add_post(user_id, channel_id, post_content, media_file_id, media_type)
            
            if post_id:
                logger.info(f"Successfully created post {post_id} for user {user_id}")
                await update.message.reply_text(
                    "✅ تم حفظ المنشور بنجاح!\n\nيمكنك الآن جدولته من 'إعدادات الجدولة'.",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                logger.error(f"Failed to create post for user {user_id}, channel {channel_id}")
                await update.message.reply_text(
                    "❌ حدث خطأ في قاعدة البيانات أثناء حفظ المنشور.\n\n"
                    "يرجى المحاولة لاحقاً أو التواصل مع المطور.",
                    reply_markup=Keyboards.back_to_main()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_post_creation for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في إنشاء المنشور: {str(e)[:100]}",
                reply_markup=Keyboards.back_to_main()
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_post_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle post editing process"""
        try:
            from keyboards import Keyboards
            from supabase_client import db
            from helpers import is_media_message
            
            user_id = update.effective_user.id
            
            try:
                post_id = int(state.split("_")[-1])
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid state format for post editing: {state}")
                await update.message.reply_text(
                    "❌ خطأ في معرف المنشور. سيتم إعادة تعيين الحالة.",
                    reply_markup=Keyboards.main_menu()
                )
                self.user_states.pop(user_id, None)
                return
            
            # Get new content
            new_content = update.message.text or update.message.caption
            new_media_file_id = None
            new_media_type = None
            
            # Check for media
            has_media, new_media_type, new_media_file_id = is_media_message(update.message)
            
            if not new_content and not has_media:
                await update.message.reply_text(
                    "❌ يجب أن يحتوي المنشور على نص أو ميديا على الأقل.\n\n"
                    "أرسل المحتوى الجديد مرة أخرى أو اضغط 'إلغاء'."
                )
                return
            
            logger.info(f"Editing post {post_id} for user {user_id}, new content length: {len(new_content or '')}, new media: {new_media_type}")
            
            # Update post
            success = await db.update_post(post_id, user_id, new_content, new_media_file_id, new_media_type)
            
            if success:
                logger.info(f"Successfully updated post {post_id} for user {user_id}")
                await update.message.reply_text(
                    "✅ تم تحديث المنشور بنجاح!",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                logger.error(f"Failed to update post {post_id} for user {user_id}")
                await update.message.reply_text(
                    "❌ حدث خطأ في قاعدة البيانات أثناء تحديث المنشور.\n\n"
                    "تأكد من أن المنشور ما زال موجود ولك صلاحية تعديله.",
                    reply_markup=Keyboards.back_to_main()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_post_editing for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في تعديل المنشور: {str(e)[:100]}",
                reply_markup=Keyboards.back_to_main()
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_scheduling_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, state: str):
        """Handle scheduling time input"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text
            
            logger.info(f"Handling scheduling input for user {user_id}, state: {state}, input: {message_text}")
            
            # Parse state to get scheduling info
            parts = state.split("_")
            if len(parts) < 3:
                logger.error(f"Invalid scheduling state format: {state}")
                await update.message.reply_text(
                    "❌ حالة جدولة غير صحيحة. سيتم إعادة التعيين.",
                    reply_markup=Keyboards.main_menu()
                )
                self.user_states.pop(user_id, None)
                return
            
            schedule_type = parts[1]  # e.g., "daily", "weekly", "once", "custom"
            
            try:
                post_id = int(parts[2])
            except (ValueError, IndexError):
                logger.error(f"Invalid post ID in scheduling state: {state}")
                await update.message.reply_text(
                    "❌ معرف المنشور غير صحيح. سيتم إعادة التعيين.",
                    reply_markup=Keyboards.main_menu()
                )
                self.user_states.pop(user_id, None)
                return
            
            # Handle different scheduling inputs based on type
            if schedule_type in ["daily", "2days"]:
                await self.handle_time_input(update, context, post_id, schedule_type, message_text)
            elif schedule_type == "weekly":
                if len(parts) == 3:  # waiting for weekday selection
                    # This should be handled in callback handlers
                    await update.message.reply_text(
                        "❌ يرجى اختيار اليوم من الأزرار المعروضة."
                    )
                elif len(parts) == 4:  # waiting for time input after weekday selection
                    try:
                        weekday = int(parts[3])
                        await self.handle_time_input(update, context, post_id, schedule_type, message_text, weekday)
                    except ValueError:
                        await update.message.reply_text(
                            "❌ خطأ في يوم الأسبوع. يرجى البدء من جديد.",
                            reply_markup=Keyboards.main_menu()
                        )
                        self.user_states.pop(user_id, None)
            elif schedule_type == "once":
                await self.handle_once_scheduling(update, context, post_id, message_text)
            elif schedule_type == "custom":
                await self.handle_custom_cron(update, context, post_id, message_text)
            else:
                logger.error(f"Unknown schedule type: {schedule_type}")
                await update.message.reply_text(
                    f"❌ نوع جدولة غير معروف: {schedule_type}\n\nسيتم إعادة التعيين.",
                    reply_markup=Keyboards.main_menu()
                )
                self.user_states.pop(user_id, None)
                
        except Exception as e:
            logger.error(f"Error in handle_scheduling_input for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في معالجة الجدولة: {str(e)[:100]}",
                reply_markup=Keyboards.main_menu()
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_time_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                               post_id: int, schedule_type: str, time_text: str, weekday: int = None):
        """Handle time input for scheduling"""
        try:
            from helpers import parse_time_string, create_cron_expression, get_next_occurrence
            from keyboards import Keyboards
            from supabase_client import db
            
            user_id = update.effective_user.id
            
            logger.info(f"Processing time input for user {user_id}: {time_text}, schedule_type: {schedule_type}, weekday: {weekday}")
            
            # Parse time
            time_obj = parse_time_string(time_text)
            if not time_obj:
                await update.message.reply_text(
                    f"❌ صيغة الوقت غير صحيحة: '{time_text}'\n\n"
                    "يرجى استخدام صيغة HH:MM مثل:\n"
                    "• 14:30\n"
                    "• 09:15\n"
                    "• 23:45",
                    reply_markup=Keyboards.time_input_help()
                )
                return
            
            # Create cron expression
            try:
                cron_expr = create_cron_expression(schedule_type, time_obj, weekday)
                if not cron_expr:
                    await update.message.reply_text(
                        f"❌ حدث خطأ في إنشاء تعبير الجدولة.\n\n"
                        f"المعطيات: نوع={schedule_type}, وقت={time_text}, يوم={weekday}"
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                logger.info(f"Created cron expression: {cron_expr}")
            except Exception as cron_error:
                logger.error(f"Error creating cron expression: {cron_error}")
                await update.message.reply_text(
                    f"❌ خطأ في إنشاء تعبير الجدولة: {str(cron_error)[:100]}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Get next run time
            try:
                next_run = get_next_occurrence(cron_expr)
                if not next_run:
                    await update.message.reply_text(
                        f"❌ حدث خطأ في حساب الوقت القادم للتعبير: {cron_expr}"
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                logger.info(f"Next run time: {next_run}")
            except Exception as time_error:
                logger.error(f"Error calculating next run time: {time_error}")
                await update.message.reply_text(
                    f"❌ خطأ في حساب الوقت القادم: {str(time_error)[:100]}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Get post and channel info
            try:
                post = await db.get_post_by_id(post_id)
                if not post:
                    await update.message.reply_text(
                        f"❌ لم يتم العثور على المنشور (ID: {post_id}).\n\n"
                        "قد يكون المنشور محذوف أو لا تملك صلاحية الوصول إليه."
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                channel = await db.get_channel_by_id(post['channel_id'])
                if not channel:
                    await update.message.reply_text(
                        f"❌ لم يتم العثور على القناة المرتبطة بالمنشور.\n\n"
                        "قد تكون القناة محذوفة من البوت."
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                logger.info(f"Found post {post_id} in channel {channel['channel_name']}")
            except Exception as db_error:
                logger.error(f"Database error when getting post/channel info: {db_error}")
                await update.message.reply_text(
                    f"❌ خطأ في قاعدة البيانات: {str(db_error)[:100]}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Save schedule
            try:
                schedule_id = await db.add_schedule(
                    post_id, channel['channel_tg_id'], user_id, cron_expr, next_run
                )
                
                if schedule_id:
                    logger.info(f"Successfully created schedule {schedule_id} for post {post_id}")
                    from helpers import format_datetime_arabic
                    next_run_formatted = format_datetime_arabic(next_run)
                    
                    await update.message.reply_text(
                        f"✅ تمت جدولة المنشور بنجاح!\n\n"
                        f"📺 القناة: {channel['channel_name']}\n"
                        f"⏰ الموعد القادم: {next_run_formatted}\n"
                        f"🔧 تعبير الجدولة: {cron_expr}",
                        reply_markup=Keyboards.main_menu()
                    )
                else:
                    logger.error(f"Failed to save schedule for post {post_id}")
                    await update.message.reply_text(
                        "❌ حدث خطأ في قاعدة البيانات أثناء حفظ الجدولة.\n\n"
                        "يرجى المحاولة لاحقاً أو التواصل مع المطور.",
                        reply_markup=Keyboards.main_menu()
                    )
                
            except Exception as schedule_error:
                logger.error(f"Error saving schedule: {schedule_error}")
                await update.message.reply_text(
                    f"❌ خطأ في حفظ الجدولة: {str(schedule_error)[:100]}",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_time_input for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في معالجة الوقت: {str(e)[:100]}",
                reply_markup=Keyboards.main_menu()
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def handle_once_scheduling(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                   post_id: int, datetime_text: str):
        """Handle one-time scheduling"""
        from keyboards import Keyboards
        
        logger.info(f"One-time scheduling requested for post {post_id} with input: {datetime_text}")
        
        await update.message.reply_text(
            "⚠️ الجدولة لمرة واحدة قيد التطوير حالياً.\n\n"
            "الميزات المتاحة:\n"
            "• الجدولة اليومية\n"
            "• الجدولة كل يومين\n"
            "• الجدولة الأسبوعية\n"
            "• الجدولة المخصصة (Cron)\n\n"
            "يرجى استخدام إحدى هذه الميزات حالياً.",
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
            
            logger.info(f"Processing custom cron for user {user_id}: {cron_text}")
            
            # Validate cron expression
            try:
                if not validate_cron_expression(cron_text):
                    await update.message.reply_text(
                        f"❌ صيغة Cron غير صحيحة: '{cron_text}'\n\n"
                        "أمثلة صحيحة:\n"
                        "• `0 9 * * *` - يومياً في 9:00\n"
                        "• `30 14 * * 1` - كل إثنين في 14:30\n"
                        "• `0 */6 * * *` - كل 6 ساعات\n"
                        "• `15 8 * * 1-5` - أيام الأسبوع في 8:15",
                        parse_mode='Markdown'
                    )
                    return
            except Exception as validation_error:
                logger.error(f"Error validating cron expression: {validation_error}")
                await update.message.reply_text(
                    f"❌ خطأ في التحقق من تعبير Cron: {str(validation_error)[:100]}"
                )
                return
            
            # Get next run time
            try:
                next_run = get_next_occurrence(cron_text)
                if not next_run:
                    await update.message.reply_text(
                        f"❌ لا يمكن حساب الوقت القادم للتعبير: {cron_text}\n\n"
                        "تأكد من صحة التعبير أو جرب تعبير آخر."
                    )
                    self.user_states.pop(user_id, None)
                    return
            except Exception as time_error:
                logger.error(f"Error calculating next occurrence: {time_error}")
                await update.message.reply_text(
                    f"❌ خطأ في حساب الوقت القادم: {str(time_error)[:100]}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Get post and channel info
            try:
                post = await db.get_post_by_id(post_id)
                if not post:
                    await update.message.reply_text(
                        f"❌ لم يتم العثور على المنشور (ID: {post_id})."
                    )
                    self.user_states.pop(user_id, None)
                    return
                
                channel = await db.get_channel_by_id(post['channel_id'])
                if not channel:
                    await update.message.reply_text(
                        "❌ لم يتم العثور على القناة المرتبطة بالمنشور."
                    )
                    self.user_states.pop(user_id, None)
                    return
            except Exception as db_error:
                logger.error(f"Database error in custom cron: {db_error}")
                await update.message.reply_text(
                    f"❌ خطأ في قاعدة البيانات: {str(db_error)[:100]}"
                )
                self.user_states.pop(user_id, None)
                return
            
            # Save schedule
            try:
                schedule_id = await db.add_schedule(
                    post_id, channel['channel_tg_id'], user_id, cron_text, next_run
                )
                
                if schedule_id:
                    logger.info(f"Successfully created custom cron schedule {schedule_id}")
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
                    logger.error(f"Failed to save custom cron schedule for post {post_id}")
                    await update.message.reply_text(
                        "❌ حدث خطأ أثناء حفظ الجدولة المخصصة.",
                        reply_markup=Keyboards.main_menu()
                    )
            except Exception as schedule_error:
                logger.error(f"Error saving custom cron schedule: {schedule_error}")
                await update.message.reply_text(
                    f"❌ خطأ في حفظ الجدولة المخصصة: {str(schedule_error)[:100]}",
                    reply_markup=Keyboards.main_menu()
                )
            
            self.user_states.pop(user_id, None)
            
        except Exception as e:
            logger.error(f"Error in handle_custom_cron for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في الجدولة المخصصة: {str(e)[:100]}",
                reply_markup=Keyboards.main_menu()
            )
            self.user_states.pop(update.effective_user.id, None)
    
    async def cancel_current_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current user action"""
        try:
            from keyboards import Keyboards
            
            user_id = update.effective_user.id
            previous_state = self.user_states.get(user_id)
            
            self.user_states.pop(user_id, None)
            
            logger.info(f"User {user_id} cancelled action. Previous state: {previous_state}")
            
            await update.message.reply_text(
                "❌ تم إلغاء العملية الحالية.\n\nيمكنك البدء من جديد.",
                reply_markup=Keyboards.main_menu()
            )
            
        except Exception as e:
            logger.error(f"Error in cancel_current_action for user {update.effective_user.id}: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ حدث خطأ في الإلغاء: {str(e)[:100]}\n\n"
                "سيتم إعادة التعيين تلقائياً."
            )

# Global instance
user_handlers = UserHandlers()