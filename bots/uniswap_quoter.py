import json
from web3 import Web3

UNISWAP_V2_ROUTER_ADDRESS = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"
UNISWAP_V3_QUOTER_ADDRESS = "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6"
UNISWAP_V2_ROUTER_ABI = json.loads(open(f"abi/UniswapV2Router.json", "r").read())
UNISWAP_V3_QUOTER_ABI = json.loads(open(f"abi/UniswapV3Quoter.json", "r").read())


class UniswapQuoter:
    def __init__(self, w3):
        self.w3 = w3
        self.v2_router = w3.eth.contract(address=UNISWAP_V2_ROUTER_ADDRESS, abi=UNISWAP_V2_ROUTER_ABI)
        self.v3_quoter = w3.eth.contract(address=UNISWAP_V3_QUOTER_ADDRESS, abi=UNISWAP_V3_QUOTER_ABI)

    # "amount_in" is int: amount of "token_in" in "token_in" decimals (i.e. 10^18 for 1 DAI, 10^6 for 1 USDC)
    # "path" is list:
    #   for V2: [token_in, token1, token2, ..., token_out]
    #   for V3: [token_in, fee1, token1, fee2, token2, ..., token_out]
    def estimate_amount_out(self, amount_in, path):
        if self.is_valid_v2_path(path):
            return self.estimate_amount_out_v2(amount_in, path)
        elif self.is_valid_v3_path(path):
            return self.estimate_amount_out_v3(amount_in, path)
        raise Exception("invalid path")

    # "path" is list: [token_in, token1, token2, ..., token_out]
    def estimate_amount_out_v2(self, amount_in, path):
        self.verify_v2_path(path)
        if amount_in == 0:
            return 0
        amount_out = self.v2_router.functions.getAmountsOut(amount_in, path).call()[-1]
        return amount_out

    # "path" is list: [token_in, fee1, token1, fee2, token2, ..., token_out]
    def estimate_amount_out_v3(self, amount_in, path):
        self.verify_v3_path(path)
        if amount_in == 0:
            return 0
        if len(path) == 3:
            [token_in, fee, token_out] = path
            sqrt_price_limit_x96 = 0
            return self.v3_quoter.functions.quoteExactInputSingle(
                token_in, token_out, fee, amount_in, sqrt_price_limit_x96
            ).call()
        encoded_path = self.encode_v3_path(path)
        return self.v3_quoter.functions.quoteExactInput(encoded_path, amount_in).call()

    # "path" is list: [token_in, fee1, token1, fee2, token2, ..., token_out]
    @staticmethod
    def encode_v3_path(path):
        UniswapQuoter.verify_v3_path(path)
        encoded_path = path[0]
        for i in range(1, len(path), 2):
            next_fee = hex(path[i])[2:].zfill(6)
            next_token = path[i + 1][2:]
            encoded_path += next_fee + next_token
        return encoded_path

    # "path" is list: [token_in, token1, token2, ..., token_out]
    @staticmethod
    def is_valid_v2_path(path):
        try:
            UniswapQuoter.verify_v2_path(path)
            return True
        except:
            return False

    # "path" is list: [token_in, fee1, token1, fee2, token2, ..., token_out]
    @staticmethod
    def is_valid_v3_path(path):
        try:
            UniswapQuoter.verify_v3_path(path)
            return True
        except:
            return False

    # "path" is list: [token_in, token1, token2, ..., token_out]
    @staticmethod
    def verify_v2_path(path):
        assert len(path) >= 2, "path must have at least 2 elements (token_in, token_out)"
        for el in path:
            assert Web3.isAddress(el), "path elements must have an address type"

    # "path" is list: [token_in, fee1, token1, fee2, token2, ..., token_out]
    @staticmethod
    def verify_v3_path(path):
        assert len(path) >= 3, "path must have at least 3 elements (token_in, fee, token_out)"
        assert len(path) % 2 == 1, "path length must be odd"
        for i in range(0, len(path), 2):
            assert Web3.isAddress(path[i]), "path elements on even positions (zero-based) must have an address type"
            if i + 1 < len(path):
                assert type(path[i + 1]) == int and (0 <= path[i + 1] < (1 << 24)), \
                    "path elements on odd positions (zero-based) must be uint24 integers"