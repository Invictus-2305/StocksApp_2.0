import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Force environment to load first
load_dotenv()

# Setup basic logging to see the output clearly
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Import database and broker logic
from database import init_db, get_config, list_users
from brokers.factory import BrokerFactory
import broker_integration

async def dry_run():
    print("="*60)
    print("DRY RUN: TESTING BROKER INTEGRATION LOGIC (NO ORDERS WILL BE PLACED)")
    print("="*60)
    
    # 1. Init Database Connection
    await init_db()
    
    # 2. Emulate an incoming signal
    mock_signal = {
        "symbol": "BANKNIFTY",
        "strike": 48500.0,
        "option_type": "CE",
        "entry_price": 320.0,
        "stop_loss": 285.0,
        "targets": [350.0],
        "lot_size": 15
    }
    
    # 3. MOCK the factory to return a Fake Broker that just prints credentials
    class FakeBroker:
        def __init__(self, name):
            self.name = name
            
        async def authenticate(self, user_config: dict) -> bool:
            print(f"\n---> [FAKE BROKER] Authenticating with {self.name}...")
            print("     Credentials received by FakeBroker:")
            if self.name == "angelone":
                print(f"       - API Key: {user_config.get('angelone_api_key')}")
                print(f"       - Client Code: {user_config.get('angelone_client_code')}")
            return True
            
        async def place_bracket_order(self, signal: dict, quantity: int) -> dict:
            print(f"---> [FAKE BROKER] Fake order placed for {quantity} qty of {signal['symbol']}.")
            return {"status": True, "message": "Dry run success", "order_id": "MOCK_ORDER_123", "symbol": signal['symbol']}

    # Override the factory's get_broker method temporarily
    original_get_broker = BrokerFactory.get_broker
    def mock_get_broker(broker_name):
        return FakeBroker(broker_name)
    
    BrokerFactory.get_broker = mock_get_broker

    # 4. Trigger the actual place_order logic from broker_integration.py
    try:
        await broker_integration.place_order(mock_signal, "MOCK_SIGNAL_ID")
    finally:
        # Restore original factory method
        BrokerFactory.get_broker = original_get_broker
        
    print("\n" + "="*60 + "\nDRY RUN COMPLETE")

if __name__ == "__main__":
    asyncio.run(dry_run())
