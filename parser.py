import re
import logging

logger = logging.getLogger(__name__)

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

    missing_fields = []

    # Extract Symbol, Strike, Option Type
    symbol_match = re.search(r"^\s*([A-Z]+)\s+(\d+(?:\.\d+)?)\s+(PE|CE)", message_text, re.MULTILINE | re.IGNORECASE)
    if symbol_match:
        result["symbol"] = symbol_match.group(1).upper()
        result["strike"] = float(symbol_match.group(2))
        result["option_type"] = symbol_match.group(3).upper()
        logger.debug(f"Parser: Symbol={result['symbol']}, Strike={result['strike']}, Type={result['option_type']}")
    else:
        missing_fields.append("symbol/strike/option_type")

    # Extract Entry Price
    entry_match = re.search(r"GOOD\s+ABOVE\s+(\d+(?:\.\d+)?)", message_text, re.IGNORECASE)
    if entry_match:
        result["entry_price"] = float(entry_match.group(1))
    else:
        missing_fields.append("entry_price")

    # Extract Stop Loss
    sl_match = re.search(r"SL\s*[:\-]?\s*(\d+(?:\.\d+)?)", message_text, re.IGNORECASE)
    if sl_match:
        result["stop_loss"] = float(sl_match.group(1))
    else:
        missing_fields.append("stop_loss")

    # Extract Targets
    tgt_match = re.search(r"TGT\s*[:\-]?\s*([0-9\._]+)", message_text, re.IGNORECASE)
    if tgt_match:
        targets_raw = tgt_match.group(1)
        targets_list = [float(t) for t in targets_raw.split('_') if t.strip()]
        result["targets"] = targets_list
    else:
        missing_fields.append("targets")

    # Extract Lot Size (optional)
    lot_match = re.search(r"#LOT_SIZE_(\d+)", message_text, re.IGNORECASE)
    if lot_match:
        result["lot_size"] = int(lot_match.group(1))

    # Extract Risk (optional)
    risk_match = re.search(r"RISK\s*:\s*([A-Z]+)", message_text, re.IGNORECASE)
    if risk_match:
        result["risk"] = risk_match.group(1).upper()

    # Log parsing summary
    if result["symbol"]:
        logger.info(
            f"PARSE OK: {result['symbol']} {result['strike']} {result['option_type']} "
            f"| Entry={result['entry_price']} SL={result['stop_loss']} "
            f"TGT={result['targets']} Lot={result['lot_size']} Risk={result['risk']}"
        )
    else:
        logger.warning(f"PARSE FAIL: Could not extract signal. Missing: [{', '.join(missing_fields)}]")

    if missing_fields and result["symbol"]:
        logger.warning(f"PARSE PARTIAL: Extracted symbol but missing: [{', '.join(missing_fields)}]")

    return result

if __name__ == "__main__":
    # Test block
    logging.basicConfig(level=logging.DEBUG)
    sample = """
    SENSEX 74000 PE

    GOOD ABOVE 950
    SL 887
    TGT 990_1050_1120

    Only Above With Some Buffer Not Before Or At FiX
    RISK : HIGH 
    """
    print(parse_order_signal(sample))
