import asyncio
import sys
import os

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrip_master import ScripMaster
from parser import parse_order_signal

async def verify():
    print("--- Angel One Mapping Verification ---")
    
    # 1. Sample Signal
    sample_msg = """
    SENSEX 74000 PE
    GOOD ABOVE 950
    SL 887
    TGT 990_1050_1120
    """
    
    print(f"Parsing sample message...")
    signal = parse_order_signal(sample_msg)
    print(f"Parsed Signal: {signal}")
    
    # 2. Load Scrip Master
    print("\nLoading Scrip Master (this may take a few seconds)...")
    success = await ScripMaster.load()
    if not success:
        print("Failed to load Scrip Master.")
        return
        
    # 3. Map to Token
    print(f"\nMapping {signal['symbol']} {signal['strike']} {signal['option_type']}...")
    scrip = await ScripMaster.get_token(signal['symbol'], signal['strike'], signal['option_type'])
    
    if scrip:
        print(f"MATCH FOUND!")
        print(f"  Token: {scrip['token']}")
        print(f"  Symbol: {scrip['symbol']}")
        print(f"  Lot Size: {scrip['lotsize']}")
        print(f"  Expiry: {scrip['expiry']}")
        print(f"  Exchange: {scrip['exch_seg']}")
        
        # 4. Verify ROBO Params
        entry = signal['entry_price']
        sl = signal['stop_loss']
        tgt = signal['targets'][0]
        
        sq_off = round(tgt - entry, 2)
        sl_diff = round(entry - sl, 2)
        
        print(f"\nROBO Order Parameters:")
        print(f"  Entry Price: {entry}")
        print(f"  Square-off (Diff): {sq_off} (Target: {tgt})")
        print(f"  Stop-loss (Diff): {sl_diff} (SL: {sl})")
        print(f"  Final Quantity: {signal.get('lot_size') or scrip['lotsize']}")
    else:
        print("MATCH NOT FOUND. Please check if the instrument exists in the Angel One master list.")

if __name__ == "__main__":
    asyncio.run(verify())
