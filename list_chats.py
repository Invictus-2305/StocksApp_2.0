import asyncio
from telethon import TelegramClient
from database import init_db, get_config

async def main():
    await init_db()
    
    api_id_str = await get_config("telegram_api_id")
    api_hash = await get_config("telegram_api_hash")
    
    if not api_id_str or not api_hash:
        print("API credentials not found. Please run auth_telegram.py first.")
        return
        
    try:
        api_id = int(api_id_str)
    except ValueError:
        print("API ID must be a valid number.")
        return
    
    print("Connecting to Telegram...")
    # It will automatically pick up the existing 'trading_bot_session.session'
    client = TelegramClient('trading_bot_session', api_id, api_hash)
    await client.start()
    
    print("\nFetching your recent dialogs (last 30 chats, channels, and groups)...\n")
    print(f"{'Chat Name':<40} | {'Chat ID'}")
    print("-" * 65)
    
    # Iterate through the most recent dialogs
    async for dialog in client.iter_dialogs(limit=30):
        name = dialog.name or "Unknown"
        # Truncate long names for console formatting
        if len(name) > 38:
            name = name[:35] + "..."
        print(f"{name:<40} | {dialog.id}")
        
    print("\n[TIP] Copy the desired 'Chat ID' (including any minus sign) and update your .env file like this:")
    print("TELEGRAM_CHANNEL=\"-100123456789\"\n")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
