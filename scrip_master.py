import aiohttp
import aiofiles
import json
import os
import time
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

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
            logger.info("ScripMaster cache expired or missing. Downloading fresh data...")
            t0 = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(SCRIP_MASTER_URL, ssl=False) as response:
                    if response.status == 200:
                        content = await response.read()
                        async with aiofiles.open(CACHE_FILE, mode='wb') as f:
                            await f.write(content)
                        cls._last_download = current_time
                        elapsed = round(time.time() - t0, 2)
                        size_mb = round(len(content) / (1024 * 1024), 2)
                        logger.info(f"ScripMaster downloaded: {size_mb} MB in {elapsed}s")
                    else:
                        logger.error(f"ScripMaster download FAILED: HTTP {response.status}")
                        return False
        else:
            age_hrs = round((current_time - cls._last_download) / 3600, 1)
            logger.debug(f"ScripMaster cache valid (age: {age_hrs}h). Skipping download.")
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
                t0 = time.time()
                async with aiofiles.open(CACHE_FILE, mode='r') as f:
                    content = await f.read()
                    raw_data = json.loads(content)
                    cls._data = pd.DataFrame(raw_data)
                    cls._data['strike'] = pd.to_numeric(cls._data['strike'], errors='coerce') / 100.0
                    elapsed = round(time.time() - t0, 2)
                    logger.info(f"ScripMaster loaded: {len(cls._data)} instruments in {elapsed}s")
                    return True
            except Exception as e:
                logger.error(f"Error loading ScripMaster into memory: {e}", exc_info=True)
                return False
        return False

    @classmethod
    async def get_token(cls, name: str, strike: float, option_type: str):
        """
        Searches for a specific instrument and returns its details.
        """
        if cls._data is None:
            await cls.load()
            
        if cls._data is None:
            logger.error("ScripMaster data unavailable. Cannot search.")
            return None

        logger.info(f"SCRIP LOOKUP: name={name}, strike={strike}, option_type={option_type}")
        t0 = time.time()

        # Filter by name, strike, and option type (PE/CE)
        mask = (cls._data['name'] == name.upper()) & \
               (cls._data['strike'] == strike)
        
        if option_type:
            mask &= cls._data['symbol'].str.endswith(option_type.upper())
            
        results = cls._data[mask]
        
        if results.empty:
            logger.warning(f"SCRIP NOT FOUND: {name} {strike} {option_type} — no match in ScripMaster")
            return None
            
        # If multiple results, prioritize nearest expiry
        if len(results) > 1:
            logger.debug(f"Multiple matches ({len(results)}) for {name} {strike} {option_type}. Picking nearest expiry.")
            valid_expiry = results[results['expiry'] != ""].copy()
            if not valid_expiry.empty:
                valid_expiry['expiry_dt'] = pd.to_datetime(valid_expiry['expiry'], format='%d%b%Y')
                # Filter out expired contracts (midnight of today)
                now = pd.Timestamp.now().normalize()
                future_expiry = valid_expiry[valid_expiry['expiry_dt'] >= now]
                
                if not future_expiry.empty:
                    nearest = future_expiry.sort_values(by='expiry_dt').iloc[0]
                else:
                    nearest = valid_expiry.sort_values(by='expiry_dt').iloc[-1]
            else:
                nearest = results.iloc[0]
        else:
            nearest = results.iloc[0]

        elapsed_ms = round((time.time() - t0) * 1000, 1)
        result = {
            "token": nearest['token'],
            "symbol": nearest['symbol'],
            "lotsize": int(nearest['lotsize']),
            "expiry": nearest['expiry'],
            "exch_seg": nearest['exch_seg']
        }
        
        logger.info(
            f"SCRIP FOUND: {result['symbol']} | token={result['token']} "
            f"exchange={result['exch_seg']} expiry={result['expiry']} "
            f"lotsize={result['lotsize']} (lookup: {elapsed_ms}ms)"
        )
        return result

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.DEBUG)
    async def test():
        success = await ScripMaster.load()
        if success:
            res = await ScripMaster.get_token("NIFTY", 22900, "PE")
            print(f"Test Result: {res}")
            
    asyncio.run(test())
