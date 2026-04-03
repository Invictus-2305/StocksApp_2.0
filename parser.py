import re

def parse_order_signal(message_text: str) -> dict:
    """
    Parses the trading signal from the telegram message.
    """
    result = {
        "symbol": None,
        "strike": None,
        "option_type": None,
        "entry_price": None,
        "stop_loss": None,
        "targets": [],
        "lot_size": None,
        "risk": None,
        "raw_message": message_text
    }

    # Extract Symbol, Strike, Option Type
    # e.g. "SOLARINDS 12500 PE" or "NIFTY 22900 PE"
    # Looking for a line that has Capitalized Words followed by Number and PE/CE
    symbol_match = re.search(r"^([A-Z]+)\s+(\d+(?:\.\d+)?)\s+(PE|CE)", message_text, re.MULTILINE | re.IGNORECASE)
    if symbol_match:
        result["symbol"] = symbol_match.group(1).upper()
        result["strike"] = float(symbol_match.group(2))
        result["option_type"] = symbol_match.group(3).upper()

    # Extract Entry Price
    # e.g. "GOOD ABOVE 140"
    entry_match = re.search(r"GOOD\s+ABOVE\s+(\d+(?:\.\d+)?)", message_text, re.IGNORECASE)
    if entry_match:
        result["entry_price"] = float(entry_match.group(1))

    # Extract Stop Loss
    # e.g. "SL 108"
    sl_match = re.search(r"SL\s*[:\-]?\s*(\d+(?:\.\d+)?)", message_text, re.IGNORECASE)
    if sl_match:
        result["stop_loss"] = float(sl_match.group(1))

    # Extract Targets
    # e.g. "TGT 163_200_250" or "TGT 24_32_45"
    tgt_match = re.search(r"TGT\s*[:\-]?\s*([0-9\._]+)", message_text, re.IGNORECASE)
    if tgt_match:
        targets_raw = tgt_match.group(1)
        # Split by underscore, remove empty strings, convert to float
        targets_list = [float(t) for t in targets_raw.split('_') if t.strip()]
        result["targets"] = targets_list

    # Extract Lot Size (optional)
    # e.g. "#LOT_SIZE_150"
    lot_match = re.search(r"#LOT_SIZE_(\d+)", message_text, re.IGNORECASE)
    if lot_match:
        result["lot_size"] = int(lot_match.group(1))

    # Extract Risk (optional)
    # e.g. "RISK : HIGH"
    risk_match = re.search(r"RISK\s*:\s*([A-Z]+)", message_text, re.IGNORECASE)
    if risk_match:
        result["risk"] = risk_match.group(1).upper()

    return result

if __name__ == "__main__":
    # Test block
    sample = """
    ======================================
    #Stock_Option

    SOLARINDS 12500 PE

    GOOD ABOVE 140
    SL 108
    TGT 163_200_250

    #LOT_SIZE_150
    RISK  : HIGH 
    -------------------------------------------
    """
    print(parse_order_signal(sample))
