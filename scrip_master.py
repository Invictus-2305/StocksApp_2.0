import aiohttp
import aiofiles
import json
import os
import time
import pandas as pd
from datetime import datetime

SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_FILE = "scrip_master.json"
CACHE_EXPIRY = 24 * 3600  # 24 hours

class ScripMaster:
    _data = None
    _last_download = 0

    @classmethod
    async def _download_if_needed(cls):
        """
        Downloads the scrip master if not already present or expired.
        """
        current_time = time.time()
        if os.path.exists(CACHE_FILE):
            cls._last_download = os.path.getmtime(CACHE_FILE)
            
        if not os.path.exists(CACHE_FILE) or (current_time - cls._last_download > CACHE_EXPIRY):
            print("Downloading Angel One Scrip Master...")
            async with aiohttp.ClientSession() as session:
                # Disable SSL verification if it fails on local systems (common on macOS)
                async with session.get(SCRIP_MASTER_URL, ssl=False) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(CACHE_FILE, mode='wb') as f:
                            await f.write(content)
                        cls._last_download = current_time
                    else:
                        print(f"Failed to download Scrip Master: {response.status}")
                        return False
        return True

    @classmethod
    async def load(cls):
        """
        Loads the scrip master into memory as a pandas DataFrame for fast searching.
        """
        if cls._data is not None and (time.time() - cls._last_download < CACHE_EXPIRY):
            return True
            
        if await cls._download_if_needed():
            try:
                async with aiofiles.open(CACHE_FILE, mode='r') as f:
                    content = await f.read()
                    raw_data = json.loads(content)
                    cls._data = pd.DataFrame(raw_data)
                    # Convert strike to numeric for easier comparison
                    # Usually strike is multiplied by 100 in master
                    cls._data['strike'] = pd.to_numeric(cls._data['strike'], errors='coerce') / 100.0
                    return True
            except Exception as e:
                print(f"Error loading Scrip Master: {e}")
                return False
        return False

    @classmethod
    async def get_token(cls, name: str, strike: float, option_type: str, exchange: str = "NFO"):
        """
        Searmches for a specific instrument and returns its details.
        """
        if cls._data is None:
            await cls.load()
            
        if cls._data is None:
            return None

        # Filter by name, strike, and option type (PE/CE)
        # Note: 'symbol' in master usually contains the full name like 'NIFTY25APR2422000PE'
        # 'name' is the base asset like 'NIFTY'
        
        mask = (cls._data['name'] == name.upper()) & \
               (cls._data['strike'] == strike) & \
               (cls._data['exch_seg'] == exchange)
        
        if option_type:
            # For options, check the symbol end for PE/CE or instrument type
            mask &= cls._data['symbol'].str.endswith(option_type.upper())
            
        results = cls._data[mask]
        
        if results.empty:
            print(f"No match found for {name} {strike} {option_type}")
            return None
            
        # If multiple results (different expiries), pick the nearest one
        if len(results) > 1:
            # Filter for results with valid expiry dates
            valid_expiry = results[results['expiry'] != ""].copy()
            if not valid_expiry.empty:
                # Convert expiry to datetime for sorting (format: 25APR2024)
                valid_expiry['expiry_dt'] = pd.to_datetime(valid_expiry['expiry'], format='%d%b%Y')
                nearest = valid_expiry.sort_values(by='expiry_dt').iloc[0]
            else:
                nearest = results.iloc[0]
        else:
            nearest = results.iloc[0]
            
        return {
            "token": nearest['token'],
            "symbol": nearest['symbol'],
            "lotsize": int(nearest['lotsize']),
            "expiry": nearest['expiry']
        }

if __name__ == "__main__":
    # Test
    import asyncio
    async def test():
        success = await ScripMaster.load()
        if success:
            res = await ScripMaster.get_token("NIFTY", 22900, "PE")
            print(f"Test Result: {res}")
            
    asyncio.run(test())
