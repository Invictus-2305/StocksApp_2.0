import asyncio
import os
from dotenv import load_dotenv
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    print("Please run this script inside your virtual environment.")
    exit(1)

# Load environment variables (MONGO_URI)
load_dotenv()

async def inspect_broker_configs():
    # Connect to MongoDB
    mongo_uri = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    print(f"Connecting to DB using: {mongo_uri.split('@')[-1] if '@' in mongo_uri else mongo_uri}")
    client = AsyncIOMotorClient(mongo_uri)
    db = client.trading_app
    
    # Fetch all users
    users = await db.users.find().to_list(100)
    print(f"\nFound {len(users)} users. Inspecting Broker Configs:\n" + "="*50)
    
    for u in users:
        username = u.get("username")
        broker_config = u.get("broker_config", {})
        pref = broker_config.get("broker_preference", "None Selected")
        
        print(f"User: {username} | Execution Enabled: {u.get('execution_enabled', False)}")
        print(f"Broker Preference: {pref}")
        
        if pref == "angelone":
            print(f"  - Client Code : {broker_config.get('angelone_client_code')}")
            print(f"  - API Key     : {broker_config.get('angelone_api_key')}")
            print(f"  - PIN         : {'***' if broker_config.get('angelone_pin') else 'None'}")
            print(f"  - TOTP Secret : {'***' if broker_config.get('angelone_totp_secret') else 'None'}")
        elif pref == "zerodha":
            print(f"  - API Key    : {broker_config.get('zerodha_api_key')}")
            print(f"  - API Secret : {'***' if broker_config.get('zerodha_api_secret') else 'None'}")
        else:
             print("  - Raw Config Dict:", broker_config)
             
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(inspect_broker_configs())
