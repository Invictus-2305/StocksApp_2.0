import pytest
from parser import parse_order_signal

def test_parse_solarinds():
    msg = """
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
    res = parse_order_signal(msg)
    assert res["symbol"] == "SOLARINDS"
    assert res["strike"] == 12500.0
    assert res["option_type"] == "PE"
    assert res["entry_price"] == 140.0
    assert res["stop_loss"] == 108.0
    assert res["targets"] == [163.0, 200.0, 250.0]
    assert res["lot_size"] == 150
    assert res["risk"] == "HIGH"

def test_parse_nifty():
    msg = """
==============================
NIFTY 22900 PE

GOOD ABOVE 190
SL 170
TGT 200_215_235

Only Above With Some Buffer Not Before Or At FiX
RISK : HIGH 
-------------------------------------------
    """
    res = parse_order_signal(msg)
    assert res["symbol"] == "NIFTY"
    assert res["strike"] == 22900.0
    assert res["option_type"] == "PE"
    assert res["entry_price"] == 190.0
    assert res["stop_loss"] == 170.0
    assert res["targets"] == [200.0, 215.0, 235.0]
    assert res["lot_size"] is None
    assert res["risk"] == "HIGH"

def test_parse_mazdock():
    msg = """
==================================
#Stock_Option

MAZDOCK 2200 PE

GOOD ABOVE 19.5
SL 08
TGT 24_32_45

#LOT_SIZE_200
RISK  : HIGH 
-------------------------------------------
    """
    res = parse_order_signal(msg)
    assert res["symbol"] == "MAZDOCK"
    assert res["strike"] == 2200.0
    assert res["option_type"] == "PE"
    assert res["entry_price"] == 19.5
    assert res["stop_loss"] == 8.0
    assert res["targets"] == [24.0, 32.0, 45.0]
    assert res["lot_size"] == 200
    assert res["risk"] == "HIGH"
