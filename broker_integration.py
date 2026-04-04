from database import get_config, list_users
from brokers.factory import BrokerFactory
import logging

logger = logging.getLogger(__name__)

async def place_order(signal_data, signal_id):
    """
    Orchestrates order placement across all eligible users via the modular broker system.
    """
    # 1. Check Global Kill Switch (Admin control)
    global_execution = await get_config("global_execution", False)
    if not global_execution:
        logger.info(f"Signal {signal_id}: Global execution is DISABLED. Skipping.")
        return False
        
    # 2. Get active brokers and all users
    active_brokers = await get_config("active_brokers", {})
    users = await list_users()
    
    logger.info(f"Processing Signal {signal_id} for {len(users)} users...")
    
    for u in users:
        username = u.get("username")
        
        # 3. Skip if User Execution is disabled
        if not u.get("execution_enabled", False):
            continue
            
        # 4. Identify User Broker Choice
        broker_config = u.get("broker_config", {})
        broker_name = broker_config.get("broker_preference")
        
        if not broker_name:
            logger.warning(f"User '{username}': No broker selected. Skipping.")
            continue
            
        # 5. Check if THIS Broker is globally enabled by Admin
        if not active_brokers.get(broker_name, False):
            logger.info(f"User '{username}': Broker '{broker_name}' is globally disabled. Skipping.")
            continue
            
        # 6. Use Factory to get Broker Instance
        broker_inst = BrokerFactory.get_broker(broker_name)
        if not broker_inst:
            logger.error(f"User '{username}': Implementation for '{broker_name}' not found.")
            continue
            
        # 7. Authenticate & Place Order
        try:
            logger.info(f"User '{username}': Authenticating with {broker_name}...")
            auth_success = await broker_inst.authenticate(broker_config)
            
            if auth_success:
                # Use signal's lot_size if provided, else it'll fallback in broker
                qty = signal_data.get("lot_size") 
                
                result = await broker_inst.place_bracket_order(signal_data, qty)
                
                if result['status']:
                    logger.info(f"User '{username}': SUCCESS! Order placed for {result['symbol']} ID: {result['order_id']}")
                else:
                    logger.error(f"User '{username}': FAILED! Reason: {result.get('message')}")
            else:
                logger.error(f"User '{username}': Authentication failed.")
                
        except Exception as e:
            logger.error(f"User '{username}': Unexpected integration error: {e}")
            continue

    return True
