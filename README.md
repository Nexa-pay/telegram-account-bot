# Telegram Account Manager Bot

A bot to manage Telegram account sessions with PostgreSQL database.

## Features
- Add/remove Telegram accounts
- Store session strings securely
- Activate/deactivate accounts
- Track reports count
- View statistics
- Admin-only access

## Deploy on Railway

1. Click "Deploy on Railway" button
2. Add your environment variables:
   - `API_ID`: Your Telegram API ID
   - `API_HASH`: Your Telegram API hash
   - `BOT_TOKEN`: Your bot token from @BotFather
   - `ADMIN_IDS`: Comma-separated user IDs who can use the bot

3. Railway will automatically:
   - Create PostgreSQL database
   - Set up the connection string
   - Deploy your bot

## Commands
- `/start` - Start the bot
- `/add` - Add new account
- `/list` - List all accounts
- `/stats` - Show statistics
- `/activate <id>` - Activate account
- `/deactivate <id>` - Deactivate account
- `/delete <id>` - Delete account
