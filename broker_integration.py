from database import get_config, list_users, get_user_config, get_user_execution

async def place_order(signal_data, signal_id):
    """
    Simulates placing an order using the configured broker for all users who have execution enabled.
    In a real implementation, this would call KiteConnect or SmartAPI async versions.
    """
    # 1. Check Global Kill Switch
    global_execution = await get_config("global_execution", False)
    if not global_execution:
        print(f"Signal {signal_id}: Global execution is Disabled. Skipping all orders.")
        return False
        
    print(f"Processing order for Signal {signal_id} across all eligible users...")
    
    # 2. Get active brokers and all users
    active_brokers = await get_config("active_brokers", {})
    users = await list_users()
    
    for u in users:
        username = u.get("username")
        
        # 3. Check Per-User Execution Flag
        execution_enabled = u.get("execution_enabled", False)
        if not execution_enabled:
            # print(f"User '{username}': Execution disabled. Skipping.")
            continue
            
        broker_config = u.get("broker_config", {})
        broker = broker_config.get("broker_preference", "zerodha")
        
        # 4. Check Global Broker Enabled Flag
        if not active_brokers.get(broker, False):
            print(f"User '{username}': Broker '{broker}' is globally disabled by admin. Skipping.")
            continue
        
        print(f"User '{username}': Executing via {broker.upper()}...")
        print(f"  Payload: BUY {signal_data['symbol']} {signal_data['strike']} {signal_data['option_type']}")
        
        # Example Zerodha Placeholder
        if broker == "zerodha":
            api_key = broker_config.get("zerodha_api_key")
            # Initialize kite connect and place GTT/Cover order
            if api_key:
                print(f"  -> SUCCESS (Simulated Zerodha API)")
            else:
                print(f"  -> FAIL: Missing Zerodha API Key")
        
        # Example AngelOne Placeholder
        elif broker == "angelone":
            api_key = broker_config.get("angelone_api_key")
            # Initialize SmartAPI and place order
            if api_key:
                print(f"  -> SUCCESS (Simulated AngelOne API)")
            else:
                print(f"  -> FAIL: Missing AngelOne API Key")

    return True
