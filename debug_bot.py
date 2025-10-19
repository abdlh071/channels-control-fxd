#!/usr/bin/env python3
"""
Debug script to check bot connection and basic functionality
"""

import asyncio
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Load environment variables
load_dotenv()

async def debug_bot():
    """Debug bot configuration and connectivity"""
    
    # Check environment variables
    bot_token = os.getenv('BOT_TOKEN')
    admin_ids = os.getenv('ADMIN_USER_IDS', '')
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    alive_url = os.getenv('ALIVE_URL')
    
    print("🔍 Checking Environment Variables...")
    print(f"BOT_TOKEN: {'✅ Set' if bot_token else '❌ Missing'}")
    print(f"ADMIN_USER_IDS: {admin_ids if admin_ids else '❌ Missing'}")
    print(f"SUPABASE_URL: {'✅ Set' if supabase_url else '❌ Missing'}")
    print(f"SUPABASE_KEY: {'✅ Set' if supabase_key else '❌ Missing'}")
    print(f"ALIVE_URL: {alive_url if alive_url else '❌ Missing'}")
    print()
    
    if not bot_token:
        print("❌ BOT_TOKEN is missing! Please set it in your environment variables.")
        return
    
    # Test bot connection
    print("🤖 Testing Bot Connection...")
    try:
        bot = Bot(token=bot_token)
        bot_info = await bot.get_me()
        print(f"✅ Bot connected successfully!")
        print(f"   Bot Name: {bot_info.first_name}")
        print(f"   Bot Username: @{bot_info.username}")
        print(f"   Bot ID: {bot_info.id}")
        print(f"   Can Join Groups: {bot_info.can_join_groups}")
        print(f"   Can Read All Group Messages: {bot_info.can_read_all_group_messages}")
        print(f"   Supports Inline Queries: {bot_info.supports_inline_queries}")
        print()
        
        # Test webhook info
        print("🌐 Checking Webhook Status...")
        webhook_info = await bot.get_webhook_info()
        print(f"   Webhook URL: {webhook_info.url or 'Not set (using polling)'}")
        print(f"   Has Custom Certificate: {webhook_info.has_custom_certificate}")
        print(f"   Pending Updates: {webhook_info.pending_update_count}")
        print(f"   Last Error Date: {webhook_info.last_error_date or 'None'}")
        if webhook_info.last_error_message:
            print(f"   Last Error: {webhook_info.last_error_message}")
        print()
        
        # Test sending a message to admin (if set)
        if admin_ids:
            admin_id_list = [int(id.strip()) for id in admin_ids.split(',') if id.strip()]
            if admin_id_list:
                print(f"📬 Testing message sending to admin {admin_id_list[0]}...")
                try:
                    test_message = await bot.send_message(
                        chat_id=admin_id_list[0],
                        text="🔧 Bot Debug Test - التشخيص يعمل بنجاح!"
                    )
                    print(f"✅ Test message sent successfully! Message ID: {test_message.message_id}")
                except TelegramError as e:
                    print(f"❌ Failed to send test message: {e}")
                print()
        
    except TelegramError as e:
        print(f"❌ Bot connection failed: {e}")
        if "Unauthorized" in str(e):
            print("   → Check if your BOT_TOKEN is correct")
            print("   → Make sure you got it from @BotFather")
        return
    
    # Test Supabase connection
    print("🗄️  Testing Supabase Connection...")
    try:
        from supabase import create_client, Client
        if supabase_url and supabase_key:
            supabase: Client = create_client(supabase_url, supabase_key)
            # Simple test query
            result = supabase.table('channels').select('id').limit(1).execute()
            print("✅ Supabase connection successful!")
        else:
            print("❌ Supabase credentials missing")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("   → Check your SUPABASE_URL and SUPABASE_KEY")
        print("   → Make sure the database schema is set up correctly")
    print()
    
    # Final recommendations
    print("📋 Troubleshooting Recommendations:")
    print("\n1. If bot doesn't respond to commands:")
    print("   • Make sure you're using the correct bot username")
    print("   • Try /start command first")
    print("   • Check if bot is blocked by your account")
    
    print("\n2. If webhook is set but bot still doesn't work:")
    print("   • Check your ALIVE_URL is accessible")
    print("   • Ensure your hosting platform supports HTTPS")
    print("   • Verify the webhook endpoint is working")
    
    print("\n3. Common issues:")
    print("   • Bot token is invalid or revoked")
    print("   • Environment variables not set correctly")
    print("   • Database connection issues")
    print("   • Hosting platform blocking requests")
    
    print("\n4. Next steps:")
    print("   • Check Render logs for any errors")
    print("   • Test bot commands directly with @BotFather")
    print("   • Verify all environment variables are set in Render")

if __name__ == "__main__":
    print("🚀 Starting Bot Debug Session...\n")
    asyncio.run(debug_bot())
    print("\n✅ Debug session completed!")