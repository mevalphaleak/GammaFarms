import json
import requests
import time

COINGECKO_API_PRICES_ENDPOINT = "https://api.coingecko.com/api/v3/simple/price"
COINGECKO_LUSD_ID = "liquity-usd"
COINGECKO_ETH_ID = "ethereum"
COINGECKO_USD_ID = "usd"

COINBASE_API_PRICES_ENDPOINT = "https://api.coinbase.com/v2/prices"
COINBASE_ETH_USD_PAIR = "ETH-USD"


def fetch_spot_price_from_coinbase(pair):
    r = requests.get(f"{COINBASE_API_PRICES_ENDPOINT}/{pair}/spot")
    return r.json()


def fetch_prices_from_coingecko(ids, vs_currencies, include_last_updated_at=True):
    params = {
        'ids': ','.join(ids),
        'vs_currencies': ','.join(vs_currencies),
        'include_last_updated_at': 'true' if include_last_updated_at else 'false',
    }
    r = requests.get(COINGECKO_API_PRICES_ENDPOINT, params)
    return r.json()


class PriceProvider:
    def __init__(self):
        self.lusd_price = None
        self.eth_price = None
        self.lusd_price_ts = None
        self.eth_price_ts = None

    def get_lusd_price(self):
        result = fetch_prices_from_coingecko([COINGECKO_LUSD_ID], [COINGECKO_USD_ID])
        self.lusd_price = result[COINGECKO_LUSD_ID][COINGECKO_USD_ID]
        self.lusd_price_ts = result[COINGECKO_LUSD_ID]['last_updated_at']
        return self.lusd_price

    def get_eth_price(self):
        now_ts = int(time.time())
        result = fetch_spot_price_from_coinbase(COINBASE_ETH_USD_PAIR)
        eth_price = float(result['data']['amount'])
        if self.eth_price is None or self.eth_price != eth_price:
            self.eth_price = eth_price
            self.eth_price_ts = now_ts
        return self.eth_price