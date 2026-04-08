from fastapi import FastAPI, Request, Response, Depends, Cookie, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database import (
    init_db, save_config, get_config, get_signals,
    create_user, get_user, verify_password, list_users, delete_user,
    save_user_config, get_user_config, set_user_execution, get_user_execution
)
from logger import setup_logging
import telegram_client
import uvicorn
import asyncio
import json
import secrets
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("========== APPLICATION STARTING ==========")
    await init_db()
    logger.info("Database initialized.")
    await telegram_client.start_telegram_listener()
    logger.info("========== APPLICATION READY ==========")
    yield
    logger.info("========== APPLICATION SHUTTING DOWN ==========")

app = FastAPI(title="Trading Automation API", lifespan=lifespan)

# Setup CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Models ----
class LoginData(BaseModel):
    username: str
    password: str

class CreateUserData(BaseModel):
    username: str
    email: str = None
    password: str
    role: str = "user"

class ConfigUpdate(BaseModel):
    telegram_api_id: str = None
    telegram_api_hash: str = None
    telegram_channel: str = None
    zerodha_api_key: str = None
    zerodha_api_secret: str = None
    broker_preference: str = None
    angelone_api_key: str = None
    angelone_client_code: str = None
    angelone_pin: str = None
    angelone_totp_secret: str = None

class BrokerToggleRequest(BaseModel):
    broker_id: str
    enabled: bool

REGISTERED_BROKERS = [
    {"id": "angelone", "name": "Angel One", "icon": "trending_up", "configKey": "angelone_api_key"},
    {"id": "zerodha", "name": "Zerodha", "icon": "candlestick_chart", "configKey": "zerodha_api_key"},
    {"id": "stoxkart", "name": "Stoxkart", "icon": "show_chart", "configKey": None},
    {"id": "ibkr", "name": "Interactive Brokers", "icon": "language", "configKey": None},
]

# ---- Session Store ----
# In-memory: { token_string: { "username": str, "role": str } }
active_sessions: dict = {}

def create_session(username: str, role: str) -> str:
    token = secrets.token_hex(32)
    active_sessions[token] = {"username": username, "role": role}
    return token

def get_session(token: str):
    return active_sessions.get(token)

def destroy_session(token: str):
    active_sessions.pop(token, None)

# ---- Auth Dependencies ----
def get_current_user(request: Request):
    """Returns the user dict {username, role} or None."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return get_session(token)

def require_login(request: Request):
    """Dependency: must be logged in."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

def require_admin(request: Request):
    """Dependency: must be admin."""
    user = require_login(request)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def require_user_role(request: Request):
    """Dependency: must be a regular user (not admin)."""
    user = require_login(request)
    if user["role"] != "user":
        raise HTTPException(status_code=403, detail="User access required")
    return user

def verify_html_session(request: Request):
    token = request.cookies.get("session_token")
    if not token or not get_session(token):
        return False
    return True

# ---- FRONTEND ROUTES ----
@app.get("/", response_class=HTMLResponse)
async def serve_login(request: Request):
    if verify_html_session(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse("templates/login.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    if not verify_html_session(request):
        return RedirectResponse(url="/", status_code=303)
    return FileResponse("templates/dashboard.html")

@app.get("/connect", response_class=HTMLResponse)
async def serve_connect(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user["role"] == "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse("templates/connect_broker.html")

@app.get("/admin/users", response_class=HTMLResponse)
async def serve_admin_users(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse("templates/admin_users.html")

@app.get("/admin/brokers", response_class=HTMLResponse)
async def serve_admin_brokers(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user["role"] != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    return FileResponse("templates/admin_brokers.html")

# ---- AUTH API ----
@app.post("/api/login")
async def login(data: LoginData, response: Response):
    user = await verify_password(data.username, data.password)
    if user:
        token = create_session(user["username"], user["role"])
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=86400 * 30 # 30 days
        )
        logger.info(f"LOGIN SUCCESS: user='{user['username']}', role='{user['role']}'")
        return {"status": "success", "role": user["role"]}
    logger.warning(f"LOGIN FAILED: user='{data.username}' — invalid credentials")
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        destroy_session(token)
    redirect = RedirectResponse(url="/", status_code=303)
    redirect.delete_cookie("session_token")
    return redirect

@app.get("/api/me")
async def get_me(user=Depends(require_login)):
    return {"username": user["username"], "role": user["role"]}

# ---- USER MANAGEMENT API (admin only) ----
@app.get("/api/users")
async def api_list_users(user=Depends(require_admin)):
    return await list_users()

@app.post("/api/users")
async def api_create_user(data: CreateUserData, user=Depends(require_admin)):
    # Check both username and email for duplicates
    existing_user = await get_user(data.username)
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    # During transition, use username as email if not provided
    effective_email = data.email or data.username
    
    from database import users_collection
    existing_email = await users_collection.find_one({"email": effective_email})
    if existing_email:
        raise HTTPException(status_code=409, detail="Email already exists")

    await create_user(data.username, data.password, data.role, email=effective_email)
    logger.info(f"USER CREATED: '{data.username}' (email={effective_email}, role={data.role}) by admin '{user['username']}'")
    return {"status": "success", "username": data.username, "email": effective_email}

@app.delete("/api/users/{username}")
async def api_delete_user(username: str, user=Depends(require_admin)):
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    success = await delete_user(username)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    logger.info(f"USER DELETED: '{username}' by admin '{user['username']}'")
    return {"status": "deleted"}

# ---- BROKER REGISTRY API ----
@app.get("/api/brokers")
async def api_get_brokers(user=Depends(require_login)):
    active_brokers = await get_config("active_brokers", {})
    response_list = []
    
    for b in REGISTERED_BROKERS:
        is_enabled = active_brokers.get(b["id"], False)
        # Admin sees everything, users only see enabled ones
        if user["role"] == "admin":
            b_copy = b.copy()
            b_copy["enabled"] = is_enabled
            response_list.append(b_copy)
        elif is_enabled:
            response_list.append(b)
            
    return response_list

@app.post("/api/admin/brokers")
async def api_toggle_broker(req: BrokerToggleRequest, user=Depends(require_admin)):
    active_brokers = await get_config("active_brokers", {})
    active_brokers[req.broker_id] = req.enabled
    await save_config("active_brokers", active_brokers)
    state = "ENABLED" if req.enabled else "DISABLED"
    logger.info(f"BROKER TOGGLE: '{req.broker_id}' {state} by admin '{user['username']}'")
    return {"status": "success", "broker_id": req.broker_id, "enabled": req.enabled}

# ---- PER-USER CONFIG API ----
@app.get("/api/config")
async def get_configuration(user=Depends(require_login)):
    username = user["username"]
    config = await get_user_config(username) or {}
    
    # Base response with global Telegram config (admins see these, users see empty/cached)
    res = {
        "telegram_api_id": await get_config("telegram_api_id", ""),
        "telegram_api_hash": await get_config("telegram_api_hash", ""),
        "telegram_channel": await get_config("telegram_channel", ""),
        "zerodha_api_key": config.get("zerodha_api_key", ""),
        "zerodha_api_secret": config.get("zerodha_api_secret", ""),
        "broker_preference": config.get("broker_preference", "angelone"),
        "angelone_api_key": config.get("angelone_api_key", ""),
        "angelone_client_code": config.get("angelone_client_code", ""),
        "angelone_pin": config.get("angelone_pin", ""),
        "angelone_totp_secret": config.get("angelone_totp_secret", ""),
    }
    return res

@app.post("/api/config")
async def update_configuration(config: ConfigUpdate, user=Depends(require_login)):
    username = user["username"]
    updated_keys = []

    # Global config
    if config.telegram_api_id is not None:
        await save_config("telegram_api_id", config.telegram_api_id)
        updated_keys.append("telegram_api_id")
    if config.telegram_api_hash is not None:
        await save_config("telegram_api_hash", config.telegram_api_hash)
        updated_keys.append("telegram_api_hash")
    if config.telegram_channel is not None:
        await save_config("telegram_channel", config.telegram_channel)
        updated_keys.append("telegram_channel")
    
    # Per-user config
    if config.zerodha_api_key is not None:
        await save_user_config(username, "zerodha_api_key", config.zerodha_api_key)
        updated_keys.append("zerodha_api_key")
    if config.zerodha_api_secret is not None:
        await save_user_config(username, "zerodha_api_secret", config.zerodha_api_secret)
        updated_keys.append("zerodha_api_secret")
    if config.broker_preference is not None:
        await save_user_config(username, "broker_preference", config.broker_preference)
        updated_keys.append(f"broker_preference={config.broker_preference}")
    if config.angelone_api_key is not None:
        await save_user_config(username, "angelone_api_key", config.angelone_api_key)
        updated_keys.append("angelone_api_key")
    if config.angelone_client_code is not None:
        await save_user_config(username, "angelone_client_code", config.angelone_client_code)
        updated_keys.append("angelone_client_code")
    if config.angelone_pin is not None:
        await save_user_config(username, "angelone_pin", config.angelone_pin)
        updated_keys.append("angelone_pin")
    if config.angelone_totp_secret is not None:
        await save_user_config(username, "angelone_totp_secret", config.angelone_totp_secret)
        updated_keys.append("angelone_totp_secret")

    logger.info(f"CONFIG UPDATED by '{username}': [{', '.join(updated_keys)}]")
    return {"status": "success"}

# ---- EXECUTION API ----
@app.get("/api/execution")
async def get_execution_state(user=Depends(require_login)):
    if user["role"] == "admin":
        global_state = await get_config("global_execution", False)
        return {"enabled": global_state, "scope": "global"}
    else:
        user_state = await get_user_execution(user["username"])
        global_state = await get_config("global_execution", False)
        return {"enabled": user_state, "global_enabled": global_state, "scope": "user"}

@app.post("/api/execution")
async def toggle_execution(request: Request, user=Depends(require_login)):
    body = await request.json()
    enabled = body.get("enabled", False)
    state = "ENABLED" if enabled else "DISABLED"
    if user["role"] == "admin":
        await save_config("global_execution", enabled)
        logger.info(f"EXECUTION TOGGLE: GLOBAL {state} by admin '{user['username']}'")
        return {"enabled": enabled, "scope": "global"}
    else:
        await set_user_execution(user["username"], enabled)
        logger.info(f"EXECUTION TOGGLE: User '{user['username']}' {state}")
        return {"enabled": enabled, "scope": "user"}

# ---- SIGNALS API ----
@app.get("/api/signals")
async def get_recent_signals(user=Depends(require_login)):
    return await get_signals()

@app.get("/api/signals/stream")
async def signal_stream(request: Request):
    """Server-Sent Events endpoint for real-time signal delivery."""
    # Verify session via cookie manually (SSE doesn't support Depends well)
    if not verify_html_session(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    async def event_generator():
        queue = telegram_client.subscribe()
        try:
            while True:
                # Wait for a new signal or send a heartbeat every 30s
                try:
                    signal = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(signal)}\n\n"
                except asyncio.TimeoutError:
                    # Send a heartbeat comment to keep the connection alive
                    yield ": heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            telegram_client.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
