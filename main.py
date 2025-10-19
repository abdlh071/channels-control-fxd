#!/usr/bin/env python3
"""
Telegram Channel Management Bot
A bot for managing channels with automated post scheduling using Supabase
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from aiohttp import web
import signal
import sys
import os

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes
)
from telegram.error import TelegramError

# Import our modules
from config import Config, setup_logging
from supabase_client import db
from user_handlers import user_handlers
from admin_handlers import admin_handlers
from callback_handlers import callback_handlers
from scheduler import PostScheduler

# Setup logging
logger = setup_logging()

class ChannelBot:
    def __init__(self):
        self.app = None
        self.scheduler = None
        self.web_app = None
    
    async def initialize(self):
        """Initialize the bot and all components"""
        try:
            # Validate configuration
            Config.validate()
            logger.info("Configuration validated successfully")
            
            # Test bot connection first
            await self.test_bot_connection()
            
            # Create bot application
            self.app = Application.builder().token(Config.BOT_TOKEN).build()
            
            # Initialize scheduler
            self.scheduler = PostScheduler(self.app)
            
            # Register handlers
            await self.register_handlers()
            
            logger.info("Bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            raise
    
    async def test_bot_connection(self):
        """Test bot connection before starting"""
        try:
            from telegram import Bot
            test_bot = Bot(token=Config.BOT_TOKEN)
            bot_info = await test_bot.get_me()
            logger.info(f"Bot connected: @{bot_info.username} (ID: {bot_info.id})")
            
            # Check current webhook status
            webhook_info = await test_bot.get_webhook_info()
            if webhook_info.url:
                logger.info(f"Current webhook: {webhook_info.url}")
                if webhook_info.pending_update_count > 0:
                    logger.warning(f"Pending updates: {webhook_info.pending_update_count}")
                if webhook_info.last_error_message:
                    logger.warning(f"Last webhook error: {webhook_info.last_error_message}")
            else:
                logger.info("No webhook set (will use polling)")
                
        except TelegramError as e:
            logger.error(f"Bot connection test failed: {e}")
            raise
    
    async def register_handlers(self):
        """Register all command and message handlers"""
        
        # Command handlers
        self.app.add_handler(CommandHandler("start", user_handlers.start_command))
        self.app.add_handler(CommandHandler("admin", admin_handlers.admin_command))
        
        # Test command for debugging
        self.app.add_handler(CommandHandler("test", self.test_command))
        
        # Message handlers (text messages only)
        self.app.add_handler(MessageHandler(
            filters.TEXT & (~filters.COMMAND),
            self.handle_message
        ))
        
        # Media message handlers
        self.app.add_handler(MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.Document.ALL |
             filters.AUDIO | filters.VOICE | filters.Sticker.ALL) & (~filters.COMMAND),
            self.handle_message
        ))
        
        # Callback query handler
        self.app.add_handler(CallbackQueryHandler(callback_handlers.handle_callback))
        
        logger.info("Handlers registered successfully")
    
    async def test_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Test command to verify bot is working"""
        logger.info(f"Test command received from user {update.effective_user.id}")
        await update.message.reply_text(
            f"✅ البوت يعمل بنجاح!\n\n"
            f"مرحباً {update.effective_user.first_name}\n"
            f"معرف المستخدم: {update.effective_user.id}\n"
            f"وقت الاختبار: {update.message.date}"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Central message handler that routes to appropriate handlers"""
        user_id = update.effective_user.id
        logger.info(f"Message received from user {user_id}: {update.message.text or '[Media]'}")
        
        # Check if admin is in broadcast mode
        if user_id in Config.ADMIN_USER_IDS:
            admin_state = user_handlers.user_states.get(user_id, "")
            if admin_state == "waiting_broadcast_message":
                await admin_handlers.handle_broadcast_message(update, context)
                return
        
        # Regular message handling
        await user_handlers.handle_text_message(update, context)
    
    async def start_scheduler(self):
        """Start the post scheduler"""
        if self.scheduler:
            # Start scheduler in background
            asyncio.create_task(self.scheduler.start_scheduler())
            logger.info("Scheduler started in background")
    
    async def setup_web_server(self):
        """Setup web server for health checks and webhook"""
        async def health_check(request):
            """Health check endpoint"""
            try:
                scheduler_status = await self.scheduler.get_scheduler_status() if self.scheduler else {"status": "not_initialized"}
                
                return web.json_response({
                    "status": "healthy",
                    "bot": "running",
                    "scheduler": scheduler_status,
                    "timestamp": asyncio.get_event_loop().time(),
                    "bot_token_set": bool(Config.BOT_TOKEN),
                    "admin_ids": len(Config.ADMIN_USER_IDS)
                })
            except Exception as e:
                logger.error(f"Health check error: {e}")
                return web.json_response({"status": "error", "message": str(e)}, status=500)
        
        async def root_handler(request):
            """Root endpoint - bot is alive"""
            return web.Response(text="🤖 Channel Management Bot is running!")
        
        async def webhook_handler(request):
            """Handle incoming webhooks from Telegram"""
            try:
                data = await request.json()
                logger.info(f"Webhook received: {data.get('update_id', 'unknown')}")
                
                if self.app:
                    update = Update.de_json(data, self.app.bot)
                    await self.app.process_update(update)
                
                return web.Response(status=200)
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return web.Response(status=500)
        
        # Create web application
        self.web_app = web.Application()
        self.web_app.router.add_get('/', root_handler)
        self.web_app.router.add_get('/health', health_check)
        self.web_app.router.add_post('/webhook', webhook_handler)
        
        # Start web server
        runner = web.AppRunner(self.web_app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', Config.PORT)
        await site.start()
        
        logger.info(f"Web server started on port {Config.PORT}")
    
    async def run(self):
        """Run the bot"""
        try:
            await self.initialize()
            
            # Setup web server for health checks
            await self.setup_web_server()
            
            # Start the scheduler
            await self.start_scheduler()
            
            # Start the bot
            logger.info("Starting Telegram bot...")
            
            # Determine if using webhook or polling
            use_webhook = (Config.ALIVE_URL and 
                          not Config.ALIVE_URL.startswith('http://localhost') and
                          not Config.ALIVE_URL.startswith('http://127.0.0.1'))
            
            if use_webhook:
                # Production - use webhook
                logger.info("Using webhook mode for production")
                await self.app.initialize()
                await self.app.start()
                
                # Set webhook
                webhook_url = f"{Config.ALIVE_URL.rstrip('/')}/webhook"
                await self.app.bot.set_webhook(
                    url=webhook_url,
                    drop_pending_updates=True
                )
                logger.info(f"Webhook set to: {webhook_url}")
                
                # Keep the application running
                while True:
                    await asyncio.sleep(60)  # Keep alive
                    
            else:
                # Development - use polling
                logger.info("Using polling mode")
                await self.app.run_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True,
                    timeout=20,
                    read_timeout=20,
                    connect_timeout=20
                )
                
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("Shutting down bot...")
        
        if self.scheduler:
            self.scheduler.stop_scheduler()
        
        if self.app:
            await self.app.shutdown()
        
        logger.info("Bot shutdown complete")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            asyncio.create_task(self.cleanup())
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point"""
    bot = ChannelBot()
    bot.setup_signal_handlers()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        sys.exit(1)