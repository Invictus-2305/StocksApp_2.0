import os
import datetime
import certifi
import bcrypt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
if "mongodb+srv" in MONGO_URI:
    client = AsyncIOMotorClient(MONGO_URI, tlsCAFile=certifi.where())
else:
    client = AsyncIOMotorClient(MONGO_URI)
db = client.trading_app

# Collections
config_collection = db.config
signals_collection = db.signals
users_collection = db.users

async def init_db():
    # MongoDB creates collections on the fly, but we can setup indexes here if needed
    await users_collection.create_index("username", unique=True)
    
    # Seed default brokers
    existing_brokers = await config_collection.find_one({"key": "active_brokers"})
    if not existing_brokers:
        await config_collection.insert_one({"key": "active_brokers", "value": {
            "angelone": True,
            "zerodha": True,
            "stoxkart": True,
            "ibkr": True
        }})
        print("Default active brokers seeded into database.")
    
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "password123")
    
    existing = await users_collection.find_one({"username": admin_username})
    if not existing:
        hashed = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt())
        await users_collection.insert_one({
            "username": admin_username,
            "password_hash": hashed.decode(),
            "role": "admin",
            "broker_config": {},
            "execution_enabled": False,
            "created_at": datetime.datetime.utcnow()
        })
        print(f"Admin user '{admin_username}' seeded into database.")
    else:
        print(f"Admin user '{admin_username}' already exists.")
        
    print("MongoDB connection initialized")

# ---- User CRUD ----
async def create_user(username: str, password: str, role: str = "user"):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    await users_collection.insert_one({
        "username": username,
        "password_hash": hashed.decode(),
        "role": role,
        "broker_config": {},
        "execution_enabled": False,
        "created_at": datetime.datetime.utcnow()
    })

async def get_user(username: str):
    return await users_collection.find_one({"username": username})

async def verify_password(username: str, password: str):
    user = await get_user(username)
    if not user:
        return None
    if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None

async def list_users():
    cursor = users_collection.find({}, {"password_hash": 0})
    users = await cursor.to_list(length=100)
    for u in users:
        u["_id"] = str(u["_id"])
        if "created_at" in u:
            u["created_at"] = u["created_at"].isoformat()
    return users

async def delete_user(username: str):
    result = await users_collection.delete_one({"username": username})
    return result.deleted_count > 0

# ---- Per-User Config ----
async def save_user_config(username: str, key: str, value):
    await users_collection.update_one(
        {"username": username},
        {"$set": {f"broker_config.{key}": value}}
    )

async def get_user_config(username: str, key: str = None, default=None):
    user = await users_collection.find_one({"username": username})
    if not user:
        return default
    config = user.get("broker_config", {})
    if key is None:
        return config
    return config.get(key, default)

async def set_user_execution(username: str, enabled: bool):
    await users_collection.update_one(
        {"username": username},
        {"$set": {"execution_enabled": enabled}}
    )

async def get_user_execution(username: str):
    user = await users_collection.find_one({"username": username})
    if not user:
        return False
    return user.get("execution_enabled", False)

# ---- Global Config (admin-level) ----
async def save_config(key: str, value):
    await config_collection.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )

async def get_config(key: str, default=None):
    doc = await config_collection.find_one({"key": key})
    return doc["value"] if doc else default

# ---- Signals ----
async def add_signal(signal_dict: dict, status: str = "PENDING"):
    signal_doc = signal_dict.copy()
    signal_doc["timestamp"] = datetime.datetime.utcnow()
    signal_doc["status"] = status
    
    result = await signals_collection.insert_one(signal_doc)
    return str(result.inserted_id)

async def get_signals(limit: int = 50):
    cursor = signals_collection.find().sort("timestamp", -1).limit(limit)
    signals = await cursor.to_list(length=limit)
    
    # Pre-process ObjectIds for JSON serialization
    for s in signals:
        s["_id"] = str(s["_id"])
        
    return signals
