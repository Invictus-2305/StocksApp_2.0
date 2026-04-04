import time
import logging
from database import get_config, list_users
from brokers.factory import BrokerFactory

logger = logging.getLogger(__name__)

async def place_order(signal_data, signal_id):
    """
    Orchestrates order placement across all eligible users via the modular broker system.
    """
    t_start = time.time()
    
    # 1. Check Global Kill Switch (Admin control)
    global_execution = await get_config("global_execution", False)
    if not global_execution:
        logger.info(f"Signal {signal_id}: Global execution is DISABLED. Skipping all orders.")
        return False
        
    # 2. Get active brokers and all users
    active_brokers = await get_config("active_brokers", {})
    users = await list_users()
    
    logger.info(
        f"{'='*50}\n"
        f"  SIGNAL {signal_id}: STARTING ORDER EXECUTION\n"
        f"  Symbol: {signal_data.get('symbol')} {signal_data.get('strike')} {signal_data.get('option_type')}\n"
        f"  Entry={signal_data.get('entry_price')} SL={signal_data.get('stop_loss')} TGT={signal_data.get('targets')}\n"
        f"  Total users: {len(users)}\n"
        f"{'='*50}"
    )
    
    # Execution counters
    eligible = 0
    success_count = 0
    fail_count = 0
    skipped = 0
    
    for u in users:
        username = u.get("username")
        
        # 3. Skip if User Execution is disabled
        if not u.get("execution_enabled", False):
            skipped += 1
            logger.debug(f"User '{username}': execution disabled. Skipping.")
            continue
            
        # 4. Identify User Broker Choice
        broker_config = u.get("broker_config", {})
        broker_name = broker_config.get("broker_preference")
        
        if not broker_name:
            skipped += 1
            logger.warning(f"User '{username}': No broker selected. Skipping.")
            continue
            
        # 5. Check if THIS Broker is globally enabled by Admin
        if not active_brokers.get(broker_name, False):
            skipped += 1
            logger.info(f"User '{username}': Broker '{broker_name}' is globally disabled. Skipping.")
            continue
            
        # 6. Use Factory to get Broker Instance
        broker_inst = BrokerFactory.get_broker(broker_name)
        if not broker_inst:
            skipped += 1
            logger.error(f"User '{username}': Implementation for '{broker_name}' not found.")
            continue
        
        eligible += 1
            
        # 7. Authenticate & Place Order
        try:
            t_user = time.time()
            logger.info(f"User '{username}': Authenticating with {broker_name}...")
            auth_success = await broker_inst.authenticate(broker_config)
            
            if auth_success:
                logger.info(f"User '{username}': Auth SUCCESS. Placing bracket order...")
                qty = signal_data.get("lot_size") 
                
                result = await broker_inst.place_bracket_order(signal_data, qty)
                elapsed_ms = round((time.time() - t_user) * 1000)
                
                if result['status']:
                    success_count += 1
                    logger.info(
                        f"User '{username}': ORDER SUCCESS | {result['symbol']} "
                        f"| OrderID={result['order_id']} | Broker={broker_name} ({elapsed_ms}ms)"
                    )
                else:
                    fail_count += 1
                    logger.error(
                        f"User '{username}': ORDER FAILED | Reason: {result.get('message')} "
                        f"| Broker={broker_name} ({elapsed_ms}ms)"
                    )
            else:
                fail_count += 1
                logger.error(f"User '{username}': Authentication FAILED for broker '{broker_name}'.")
                
        except Exception as e:
            fail_count += 1
            logger.error(f"User '{username}': Unexpected error: {e}", exc_info=True)
            continue

    # Execution Summary
    total_elapsed = round(time.time() - t_start, 2)
    logger.info(
        f"{'='*50}\n"
        f"  SIGNAL {signal_id}: EXECUTION SUMMARY\n"
        f"  Total Users: {len(users)} | Eligible: {eligible} | Skipped: {skipped}\n"
        f"  Success: {success_count} | Failed: {fail_count}\n"
        f"  Total Time: {total_elapsed}s\n"
        f"{'='*50}"
    )

    return True
