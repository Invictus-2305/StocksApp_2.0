import pyotp
import logging
from SmartApi import SmartConnect
from brokers.base import BaseBroker
from scrip_master import ScripMaster

logger = logging.getLogger(__name__)

class AngelOneBroker(BaseBroker):
    def __init__(self):
        self.smart_api = None
        self.session = None

    async def authenticate(self, user_config: dict) -> bool:
        """
        Authenticate using Client Code, Password (PIN), API Key, and TOTP.
        """
        client_code = user_config.get("angelone_client_code")
        api_key = user_config.get("angelone_api_key")
        pin = user_config.get("angelone_pin")
        totp_secret = user_config.get("angelone_totp_secret")
        
        if not all([client_code, api_key, pin, totp_secret]):
            logger.error(f"Missing Angel One credentials for user.")
            return False
            
        try:
            # Initialize SmartConnect
            self.smart_api = SmartConnect(api_key=api_key)
            
            # Generate TOTP
            totp = pyotp.TOTP(totp_secret).now()
            
            # Login
            data = self.smart_api.generateSession(client_code, pin, totp)
            
            if data['status']:
                self.session = data['data']
                return True
            else:
                logger.error(f"Angel One Login Failed for {client_code}: {data.get('message')}")
                return False
                
        except Exception as e:
            logger.error(f"Angel One Authentication Error: {e}")
            return False

    async def place_bracket_order(self, signal: dict, quantity: int) -> dict:
        """
        Place a ROBO (Bracket) Order on Angel One.
        """
        if not self.smart_api or not self.session:
            return {"status": False, "message": "Not authenticated"}
            
        try:
            # 1. Map Symbol to Token
            name = signal.get("symbol")
            strike = signal.get("strike")
            option_type = signal.get("option_type")
            
            scrip = await ScripMaster.get_token(name, strike, option_type)
            if not scrip:
                return {"status": False, "message": f"Instrument mapping failed for {name} {strike} {option_type}"}
                
            # 2. Extract Prices
            entry_price = signal.get("entry_price")
            stop_loss = signal.get("stop_loss")
            targets = signal.get("targets", [])
            
            if not entry_price or not stop_loss or not targets:
                return {"status": False, "message": "Missing signal price details (Entry/SL/TGT)"}
                
            # 3. Calculate Absolute Differences for ROBO
            squareoff_diff = round(targets[0] - entry_price, 2)
            stoploss_diff = round(entry_price - stop_loss, 2)
            
            if squareoff_diff <= 0 or stoploss_diff <= 0:
                return {"status": False, "message": f"Invalid ROBO difference: Target={squareoff_diff}, SL={stoploss_diff}"}

            # 4. Final quantity
            # Use provided quantity (from ScripMaster fallback) or signal if available
            order_qty = quantity or scrip['lotsize']
            
            # 5. Build Parameters
            broker_params = {
                "variety": "ROBO",
                "tradingsymbol": scrip['symbol'],
                "symboltoken": scrip['token'],
                "transactiontype": "BUY", # Standard for the signal
                "exchange": scrip['exch_seg'],
                "ordertype": "LIMIT",
                "producttype": "BO",
                "duration": "DAY",
                "price": str(entry_price),
                "quantity": str(order_qty),
                "squareoff": str(squareoff_diff),
                "stoploss": str(stoploss_diff)
            }
            
            # 6. Place Order
            logger.info(f"Placing Angel One ROBO Order: {broker_params}")
            order_id = self.smart_api.placeOrder(broker_params)
            
            return {"status": True, "order_id": order_id, "symbol": scrip['symbol']}
            
        except Exception as e:
            logger.error(f"Angel One Order Placement Failed: {e}")
            return {"status": False, "message": str(e)}
