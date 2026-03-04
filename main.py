import asyncio
import logging
import sys
from telethon import TelegramClient, events, Button
from telethon.errors import SessionPasswordNeededError
from config import Config
from database import Database

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variables
bot = None
db = None

async def startup():
    """Initialize bot and database"""
    global bot, db
    
    logger.info("Starting up...")
    
    # Validate configuration
    try:
        Config.validate()
        logger.info("Configuration validated successfully")
        logger.info(f"API_ID: {Config.API_ID}")
        logger.info(f"API_HASH length: {len(Config.API_HASH) if Config.API_HASH else 0}")
        logger.info(f"BOT_TOKEN length: {len(Config.BOT_TOKEN) if Config.BOT_TOKEN else 0}")
        logger.info(f"ADMIN_IDS: {Config.ADMIN_IDS}")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Initialize database
    try:
        db = Database(Config.DATABASE_URL)
        await db.connect()
        await db.init_db()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        sys.exit(1)
    
    # Initialize bot
    try:
        bot = TelegramClient('bot_session', Config.API_ID, Config.API_HASH)
        await bot.start(bot_token=Config.BOT_TOKEN)
        logger.info("Bot started successfully")
        
        # Get bot info
        me = await bot.get_me()
        logger.info(f"Bot username: @{me.username}")
        
        return bot
    except Exception as e:
        logger.error(f"Bot initialization error: {e}")
        sys.exit(1)

# Store user states for adding accounts
user_states = {}

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    """Start command handler"""
    if db is None:
        return await event.respond("❌ Database not connected. Please try again later.")
    
    stats = await db.get_stats()
    
    # Check if user is authorized
    is_admin = event.sender_id in Config.ADMIN_IDS if Config.ADMIN_IDS else False
    
    if not is_admin:
        return await event.respond("❌ You are not authorized to use this bot.")
    
    text = f"""
🚀 **Telegram Account Manager Bot**

Welcome! Manage your Telegram accounts efficiently.

📊 **Statistics:**
• Total Accounts: {stats['total']}
• Active Accounts: {stats['active']}
• Inactive Accounts: {stats['inactive']}

**Commands:**
/add - ➕ Add new account
/list - 📋 List all accounts
/stats - 📊 View statistics
/activate [id] - ✅ Activate account
/deactivate [id] - ❌ Deactivate account
/delete [id] - 🗑️ Delete account
    """
    
    buttons = [
        [Button.inline("➕ Add Account", data="add")],
        [Button.inline("📋 List Accounts", data="list")],
        [Button.inline("📊 Statistics", data="stats")]
    ]
    
    await event.respond(text, buttons=buttons, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/add'))
@bot.on(events.CallbackQuery(data='add'))
async def add_account_start(event):
    """Start add account process"""
    # Check if user is admin
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ You are not authorized to use this command.")
    
    # Handle both message and callback
    if isinstance(event, events.CallbackQuery):
        await event.answer()
        chat_id = event.chat_id
    else:
        chat_id = event.chat_id
    
    user_states[chat_id] = {'step': 'phone'}
    await bot.send_message(chat_id, 
        "📱 Please send the phone number in international format:\n"
        "Example: `+1234567890`", 
        parse_mode='markdown'
    )

@bot.on(events.NewMessage)
async def handle_input(event):
    """Handle user input for adding accounts"""
    if event.sender_id not in Config.ADMIN_IDS:
        return
    
    user_id = event.chat_id
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    text = event.message.text.strip()
    
    if state['step'] == 'phone':
        # Validate phone number
        if not text.startswith('+') or not text[1:].isdigit():
            return await event.respond("❌ Invalid format! Please send phone number with country code (e.g., +1234567890)")
        
        state['phone'] = text
        state['step'] = 'session'
        await event.respond("🔑 Please send the session string for this account:")
        
    elif state['step'] == 'session':
        state['session'] = text
        state['step'] = 'confirm'
        
        # Show summary
        summary = f"""
📝 **Account Summary:**
• Phone: `{state['phone']}`
• Session: `{state['session'][:20]}...` (length: {len(state['session'])})

Is this correct?
        """
        
        buttons = [
            [Button.inline("✅ Yes, Save", data="confirm_save")],
            [Button.inline("❌ No, Cancel", data="cancel")]
        ]
        
        await event.respond(summary, buttons=buttons, parse_mode='markdown')

@bot.on(events.CallbackQuery(data='confirm_save'))
async def save_account(event):
    """Save account to database"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.answer("Unauthorized", alert=True)
    
    user_id = event.chat_id
    if user_id not in user_states:
        return await event.answer("No pending action", alert=True)
    
    state = user_states[user_id]
    
    try:
        account_id = await db.add_account(
            phone_number=state['phone'],
            session_string=state['session'],
            added_by=event.sender_id
        )
        
        await event.edit(f"""
✅ **Account saved successfully!**

**Account Details:**
• ID: `{account_id}`
• Phone: `{state['phone']}`
• Status: Active
        """, parse_mode='markdown')
        
        # Clear user state
        del user_states[user_id]
        
    except Exception as e:
        logger.error(f"Error saving account: {e}")
        await event.edit(f"❌ Error saving account: {str(e)}")

@bot.on(events.CallbackQuery(data='cancel'))
async def cancel_action(event):
    """Cancel current action"""
    user_id = event.chat_id
    if user_id in user_states:
        del user_states[user_id]
    await event.edit("❌ Action cancelled.")

@bot.on(events.NewMessage(pattern='/list'))
@bot.on(events.CallbackQuery(data='list'))
async def list_accounts(event):
    """List all accounts"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ Unauthorized")
    
    if isinstance(event, events.CallbackQuery):
        await event.answer()
        chat_id = event.chat_id
    else:
        chat_id = event.chat_id
    
    accounts = await db.get_accounts()
    
    if not accounts:
        return await bot.send_message(chat_id, "📭 No accounts found in database.")
    
    text = "**📋 Account List:**\n\n"
    for acc in accounts:
        status = "✅ Active" if acc['is_active'] else "❌ Inactive"
        text += f"**ID:** `{acc['id']}`\n"
        text += f"**Phone:** `{acc['phone_number']}`\n"
        text += f"**Status:** {status}\n"
        text += f"**Reports:** {acc['reports_count']}\n"
        text += f"**Added:** {acc['added_date'].strftime('%Y-%m-%d')}\n"
        text += "─" * 20 + "\n"
    
    # Send in chunks if too long
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await bot.send_message(chat_id, text[i:i+4000], parse_mode='markdown')
    else:
        await bot.send_message(chat_id, text, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/stats'))
@bot.on(events.CallbackQuery(data='stats'))
async def show_stats(event):
    """Show account statistics"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ Unauthorized")
    
    if isinstance(event, events.CallbackQuery):
        await event.answer()
        chat_id = event.chat_id
    else:
        chat_id = event.chat_id
    
    stats = await db.get_stats()
    accounts = await db.get_accounts()
    
    text = f"""
📊 **Database Statistics**

**Overview:**
• Total Accounts: {stats['total']}
• Active Accounts: {stats['active']}
• Inactive Accounts: {stats['inactive']}

**Details:**
• Accounts with reports: {sum(1 for a in accounts if a['reports_count'] > 0)}
• Total reports sum: {sum(a['reports_count'] for a in accounts)}
    """
    
    await bot.send_message(chat_id, text, parse_mode='markdown')

@bot.on(events.NewMessage(pattern='/activate(?:\\s+(\\d+))?'))
async def activate_account(event):
    """Activate an account"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ Unauthorized")
    
    account_id = event.pattern_match.group(1)
    if not account_id:
        return await event.respond("❌ Please provide account ID: `/activate 123`", parse_mode='markdown')
    
    try:
        account_id = int(account_id)
        success = await db.update_account_status(account_id, True)
        
        if success:
            await event.respond(f"✅ Account `{account_id}` has been activated.")
        else:
            await event.respond(f"❌ Account `{account_id}` not found.")
    except ValueError:
        await event.respond("❌ Invalid account ID format.")

@bot.on(events.NewMessage(pattern='/deactivate(?:\\s+(\\d+))?'))
async def deactivate_account(event):
    """Deactivate an account"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ Unauthorized")
    
    account_id = event.pattern_match.group(1)
    if not account_id:
        return await event.respond("❌ Please provide account ID: `/deactivate 123`", parse_mode='markdown')
    
    try:
        account_id = int(account_id)
        success = await db.update_account_status(account_id, False)
        
        if success:
            await event.respond(f"✅ Account `{account_id}` has been deactivated.")
        else:
            await event.respond(f"❌ Account `{account_id}` not found.")
    except ValueError:
        await event.respond("❌ Invalid account ID format.")

@bot.on(events.NewMessage(pattern='/delete(?:\\s+(\\d+))?'))
async def delete_account(event):
    """Delete an account"""
    if event.sender_id not in Config.ADMIN_IDS:
        return await event.respond("❌ Unauthorized")
    
    account_id = event.pattern_match.group(1)
    if not account_id:
        return await event.respond("❌ Please provide account ID: `/delete 123`", parse_mode='markdown')
    
    try:
        account_id = int(account_id)
        success = await db.delete_account(account_id)
        
        if success:
            await event.respond(f"✅ Account `{account_id}` has been deleted.")
        else:
            await event.respond(f"❌ Account `{account_id}` not found.")
    except ValueError:
        await event.respond("❌ Invalid account ID format.")

async def main():
    """Main function"""
    global bot
    
    try:
        # Initialize everything
        bot = await startup()
        
        logger.info("Bot is running...")
        await bot.run_until_disconnected()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        if db:
            await db.close()
            logger.info("Database connection closed")

if __name__ == '__main__':
    asyncio.run(main())