import asyncio
import json
import logging
from telethon import TelegramClient, events
from database import get_config, add_signal
from parser import parse_order_signal
from broker_integration import place_order

logger = logging.getLogger(__name__)

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
        logger.warning("Telegram API ID or Hash not configured. Listener NOT started.")
        return

    try:
        client = TelegramClient('trading_bot_session', int(api_id), api_hash)
        await client.connect()

        if not await client.is_user_authorized():
            logger.warning("Telegram client is NOT authorized. Please initiate login flow separately.")
            return

        if target_channel:
            try:
                chat_filter = int(target_channel)
            except ValueError:
                chat_filter = target_channel
            logger.info(f"Telegram connected. Listening to channel: {chat_filter}")
        else:
            chat_filter = None
            logger.warning("Telegram connected. WARNING: No target_channel — listening to ALL chats.")

        @client.on(events.NewMessage(chats=chat_filter))
        async def handler(event):
            msg_text = event.message.message
            logger.info(f"NEW MESSAGE received ({len(msg_text)} chars): {msg_text[:80]}...")
            
            # Parse the signal
            signal_data = parse_order_signal(msg_text)
            
            if signal_data.get("symbol"):
                logger.info(
                    f"SIGNAL PARSED: {signal_data['symbol']} {signal_data['strike']} "
                    f"{signal_data['option_type']} | Entry={signal_data.get('entry_price')} "
                    f"SL={signal_data.get('stop_loss')} TGT={signal_data.get('targets')}"
                )
                
                # Save to DB
                signal_id = await add_signal(signal_data, status="PARSED")
                logger.info(f"Signal saved to DB with ID: {signal_id}")
                
                # Broadcast to connected dashboards
                broadcast_data = signal_data.copy()
                broadcast_data["_id"] = signal_id
                broadcast_data["status"] = "PARSED"
                await _broadcast(broadcast_data)
                logger.debug(f"Signal broadcasted to {len(_signal_subscribers)} SSE clients.")
                
                # Place order via Broker Integration
                await place_order(signal_data, signal_id)
            else:
                logger.info(f"Message did not match signal pattern. Skipping.")

        logger.info("Telegram listener started. Waiting for messages...")

    except Exception as e:
        logger.error(f"Error starting Telegram client: {e}", exc_info=True)
