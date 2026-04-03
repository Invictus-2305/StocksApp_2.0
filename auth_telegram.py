import asyncio
from telethon import TelegramClient
from database import init_db, get_config, save_config

async def main():
    await init_db()
    
    print("=== Telegram Authentication Setup ===")
    
    api_id_str = await get_config("telegram_api_id")
    api_hash = await get_config("telegram_api_hash")
    
    if not api_id_str or not api_hash:
        print("API credentials not found in database.")
        api_id_str = input("Enter your Telegram App API ID: ")
        api_hash = input("Enter your Telegram App API Hash: ")
        await save_config("telegram_api_id", api_id_str)
        await save_config("telegram_api_hash", api_hash)
        
    try:
        api_id = int(api_id_str)
    except ValueError:
        print("\nError: API ID must be a number! Please run again.")
        return

    print("\nConnecting to Telegram... (You will be prompted for Phone and OTP)")
    # Initialize and start client
    # start() automatically prompts for phone number and auth code in the terminal
    client = TelegramClient('trading_bot_session', api_id, api_hash)
    await client.start()
    
    me = await client.get_me()
    print("\n[SUCCESS] Authentication complete.")
    print(f"Logged in as: {me.username or me.first_name or 'User'}")
    print("The 'trading_bot_session.session' file has been saved.")
    print("You can now safely exit this script (Ctrl+C).")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
