import asyncio
import json
from telethon import TelegramClient, events
from database import get_config, add_signal
from parser import parse_order_signal
from broker_integration import place_order

# We'll use a globally accessible client var, initialized dynamically
client = None

# SSE broadcast system: each connected browser gets a queue
_signal_subscribers: list[asyncio.Queue] = []

def subscribe() -> asyncio.Queue:
    """Register a new SSE client. Returns a queue that will receive new signals."""
    q = asyncio.Queue()
    _signal_subscribers.append(q)
    return q

def unsubscribe(q: asyncio.Queue):
    """Remove an SSE client when they disconnect."""
    _signal_subscribers.remove(q)

async def _broadcast(signal_data: dict):
    """Push a new signal to every connected SSE client."""
    for q in _signal_subscribers:
        await q.put(signal_data)

async def start_telegram_listener():
    global client
    api_id = await get_config("telegram_api_id")
    api_hash = await get_config("telegram_api_hash")
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    target_channel = os.getenv("TELEGRAM_CHANNEL") or await get_config("telegram_channel")
    
    if not api_id or not api_hash:
        print("Telegram API ID or Hash not configured. Listener not started.")
        return

    try:
        # We can't prompt for login through the FastAPI console easily,
        # so for this version, the user must login by running `python run_telethon_login.py`
        # once in the terminal, or we implement an API for it.
        # But we will instantiate it here just in case they've logged in.
        client = TelegramClient('trading_bot_session', int(api_id), api_hash)
        
        # connect (don't start automatically which requires stdin)
        await client.connect()

        if not await client.is_user_authorized():
            print("Telegram client is not authorized. Please initiate login flow separately.")
            return

        if target_channel:
            # Telethon can accept usernames ('@channel_name'), invite links, or exact integer chat IDs
            try:
                # Try to convert to an int if it's a numeric Chat ID
                chat_filter = int(target_channel)
            except ValueError:
                chat_filter = target_channel
            print(f"Telegram client connected. Restricting listener to chat: {chat_filter}")
        else:
            chat_filter = None
            print("Telegram client connected. WARNING: No target_channel configured. Listening to ALL chats.")

        @client.on(events.NewMessage(chats=chat_filter))
        async def handler(event):
            msg_text = event.message.message
            print(f"New message received: {msg_text[:50]}...")
            
            # Parse
            signal_data = parse_order_signal(msg_text)
            
            if signal_data.get("symbol"):
                print(f"Signal Parsed successfully: {signal_data}")
                # Save to DB
                signal_id = await add_signal(signal_data, status="PARSED")
                
                # Broadcast to all connected dashboards in real-time
                broadcast_data = signal_data.copy()
                broadcast_data["_id"] = signal_id
                broadcast_data["status"] = "PARSED"
                await _broadcast(broadcast_data)
                
                # Place order via Broker Integration
                await place_order(signal_data, signal_id)

        print("Listening for messages...")
        # Since we are running inside FastAPI event loop, we don't `run_until_disconnected` 
        # normally. We just await it as a background task.

    except Exception as e:
        print(f"Error starting telegram client: {e}")
