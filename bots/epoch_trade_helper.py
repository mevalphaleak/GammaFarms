import json
from eth_abi import encode_abi
from web3 import Web3

from uniswap_quoter import UniswapQuoter

DAI_ADDRESS = "0x6B175474E89094C44Da98b954EedeAC495271d0F"
LQTY_ADDRESS = "0x6DEA81C8171D0bA574754EF6F8b412F2Ed88c54D"
LUSD_ADDRESS = "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0"
MAL_ADDRESS = "0x6619078Bdd8324E01E9a8D4b3d761b050E5ECF06"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

CURVE_LUSD_POOL_ADDRESS = "0xEd279fDD11cA84bEef15AF5D39BB4d4bEE23F0cA"
CURVE_LUSD_POOL_ABI = json.loads(open(f"abi/CurveLUSDPool.json", "r").read())


class EpochTradeHelper:
    def __init__(self, w3):
        self.w3 = w3
        self.uniswap_quoter = UniswapQuoter(w3)
        self.lusd_curve_pool = w3.eth.contract(address=CURVE_LUSD_POOL_ADDRESS, abi=CURVE_LUSD_POOL_ABI)

    def build_trade_data(self, eth_amount, lqty_amount, mal_burn_pct):
        # LQTY->WETH | WETH(mal_burn%)->MAL | WETH(100%-mal_burn%)+wrap(ETH)->LUSD
        lqty_weth_path = [LQTY_ADDRESS, 3000, WETH_ADDRESS]
        weth_mal_path = [WETH_ADDRESS, 3000, MAL_ADDRESS]
        weth_amount_out = self.uniswap_quoter.estimate_amount_out(int(lqty_amount), lqty_weth_path)
        weth_to_buy_mal = self._amount_to_swap_for_mal(weth_amount_out, mal_burn_pct)
        mal_amount_out = self.uniswap_quoter.estimate_amount_out(int(weth_to_buy_mal), weth_mal_path)
        weth_to_buy_lusd = eth_amount + (weth_amount_out - weth_to_buy_mal)
        if weth_to_buy_lusd == 0:
            return b''
        (weth_lusd_path, lusd_amount_out) = self._evaluate_weth_to_lusd_options(weth_to_buy_lusd)
        weth_to_stable_token_fee = weth_lusd_path[1]
        stable_token = weth_lusd_path[2]
        use_curve_for_stable_token_to_lusd = (weth_lusd_path[-1] != LUSD_ADDRESS)
        return encode_abi(['address', 'uint24', 'bool'], [stable_token, weth_to_stable_token_fee, use_curve_for_stable_token_to_lusd])

    def _evaluate_weth_to_lusd_options(self, weth_amount):
        weth_lusd_options = [
            [WETH_ADDRESS, 3000, LUSD_ADDRESS],
            [WETH_ADDRESS, 500, USDC_ADDRESS],
            [WETH_ADDRESS, 3000, USDC_ADDRESS],
            [WETH_ADDRESS, 500, DAI_ADDRESS],
            [WETH_ADDRESS, 3000, DAI_ADDRESS],
            [WETH_ADDRESS, 500, USDC_ADDRESS, 500, LUSD_ADDRESS],
            [WETH_ADDRESS, 3000, USDC_ADDRESS, 500, LUSD_ADDRESS],
            [WETH_ADDRESS, 500, DAI_ADDRESS, 500, LUSD_ADDRESS],
            [WETH_ADDRESS, 3000, DAI_ADDRESS, 500, LUSD_ADDRESS],
        ]
        return self._pick_best_path(weth_amount, weth_lusd_options, with_curve_trade=True)

    def _pick_best_path(self, amount_in, path_options, with_curve_trade=False):
        (best_path, best_amount_out) = (None, None)
        for path in path_options:
            amount_out = None
            try:
                amount_out = self.uniswap_quoter.estimate_amount_out(int(amount_in), path)
            except Exception as e:
                print(f"Skipping path {path} with error: {e}")
                continue
            if with_curve_trade and path[-1] != LUSD_ADDRESS:
                if path[-1] == USDC_ADDRESS:
                    amount_out = self.lusd_curve_pool.functions.get_dy_underlying(2, 0, amount_out).call()
                elif path[-1] == DAI_ADDRESS:
                    amount_out = self.lusd_curve_pool.functions.get_dy_underlying(1, 0, amount_out).call()
                else:
                    raise Exception("Unexpected token")
            if (best_amount_out or 0) < amount_out:
                (best_path, best_amount_out) = (path, amount_out)
        if best_path is None:
            raise Exception("Failed to estimate amount out for given trade path options")
        return (best_path, best_amount_out)

    def _amount_to_swap_for_mal(self, amount, mal_burn_pct):
        return amount * mal_burn_pct // 10000


if __name__ == "__main__":
    from config import MAINNET_ENDPOINT
    w3 = Web3(Web3.HTTPProvider(MAINNET_ENDPOINT))
    (E18, E12, E6) = (10**18, 10**12, 10**6)
    # price feed:
    price_feed = w3.eth.contract(address="0x4c517D4e2C851CA76d7eC94B805269Df0f2201De", abi=json.loads(open(f"abi/PriceFeed.json", "r").read()))
    eth_usd_price = price_feed.functions.lastGoodPrice().call() / E18
    print(f"PriceFeed: last_good_price={eth_usd_price:.4f}")
    # quote WETH -> LUSD options:
    quoter = UniswapQuoter(w3)
    lusd_curve_pool = w3.eth.contract(address=CURVE_LUSD_POOL_ADDRESS, abi=CURVE_LUSD_POOL_ABI)
    paths = {
        "V2[WETH/LUSD]": [WETH_ADDRESS, LUSD_ADDRESS],
        "V2[WETH/USDC]": [WETH_ADDRESS, USDC_ADDRESS],
        "V3[WETH/LUSD/3000]": [WETH_ADDRESS, 3000, LUSD_ADDRESS],
        "V3[WETH/USDC/500]": [WETH_ADDRESS, 500, USDC_ADDRESS],
        "V3[WETH/USDC/3000]": [WETH_ADDRESS, 3000, USDC_ADDRESS],
        "V3[WETH/DAI/500]": [WETH_ADDRESS, 500, DAI_ADDRESS],
        "V3[WETH/DAI/3000]": [WETH_ADDRESS, 3000, DAI_ADDRESS],
        "V3[WETH/USDC/500 -> USDC/LUSD/500]": [WETH_ADDRESS, 500, USDC_ADDRESS, 500, LUSD_ADDRESS],
        "V3[WETH/USDC/3000 -> USDC/LUSD/500]": [WETH_ADDRESS, 3000, USDC_ADDRESS, 500, LUSD_ADDRESS],
        "V3[WETH/DAI/500 -> DAI/LUSD/500]": [WETH_ADDRESS, 500, DAI_ADDRESS, 500, LUSD_ADDRESS],
        "V3[WETH/DAI/3000 -> DAI/LUSD/500]": [WETH_ADDRESS, 3000, DAI_ADDRESS, 500, LUSD_ADDRESS],
    }
    amount_in = 10 * E18
    print(f"AmountIn: {amount_in/E18:.4f} WETH")
    options = []
    expected_price = eth_usd_price
    for (path_name, path) in paths.items():
        amount_out = None
        try:
            amount_out = quoter.estimate_amount_out(amount_in, path)
        except Exception as e:
            print(f"Skipping path {path_name} with error: {e}")
            continue
        # check if Curve swap needed:
        if path[-1] == LUSD_ADDRESS:
            amount_lusd_out = amount_out
        if path[-1] == USDC_ADDRESS:
            path_name += " + Curve[USDC/LUSD]"
            amount_lusd_out = lusd_curve_pool.functions.get_dy_underlying(2, 0, amount_out).call()
        if path[-1] == DAI_ADDRESS:
            path_name += " + Curve[DAI/LUSD]"
            amount_lusd_out = lusd_curve_pool.functions.get_dy_underlying(1, 0, amount_out).call()
        token_price = amount_out * (1 if path[-1] != USDC_ADDRESS else E12) / amount_in
        final_price = amount_lusd_out / amount_in
        options += [(path_name, final_price, token_price)]
    options = sorted(options, key=lambda v: -v[1])
    for (path_name, final_price, token_price) in options:
        diff_pct = 100 * (final_price - expected_price) / expected_price
        print(f"{path_name:40} {final_price:10.4f} (diff: {diff_pct:+10.4f}%, after_uni: {token_price:10.4f})")