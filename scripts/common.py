import eth_account
from decimal import Decimal

from brownie import accounts, network, Contract, TestPriceFeed
from brownie._config import CONFIG
from scripts.contracts import deploy_test_price_feed
from scripts.tokens import token_contract, LUSD_ADDRESS

DAY_SECS = 24 * 60 * 60
DEBUG = False
E18 = 10 ** 18
E18d = Decimal(10 ** 18)
UINT256_MAX = pow(2, 256) - 1

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

LUSD_COLL_SURPLUS_ADDRESS = "0x3D32e8b97Ed5881324241Cf03b2DA5E2EBcE5521"
LUSD_GAS_POOL_ADDRESS = "0x9555b042F969E561855e5F28cB1230819149A8d9"
LUSD_PRICE_FEED_ADDRESS = "0x4c517D4e2C851CA76d7eC94B805269Df0f2201De"
LUSD_SORTED_TROVES_ADDRESS = "0x8FdD3fbFEb32b28fb73555518f8b361bCeA741A6"
LUSD_STABILITY_POOL_ADDRESS = "0x66017D22b0f8556afDd19FC67041899Eb65a21bb"
LUSD_TROVE_MANAGER_ADDRESS = "0xA39739EF8b0231DbFA0DcdA07d7e29faAbCf4bb2"


def create_lusd_permit_data(user_address, spender_address, amount_wei, deadline, nonce=None):
    if nonce is None:
        lusd = token_contract(LUSD_ADDRESS)
        nonce = lusd.nonces(user_address)

    return {
        'domain': {
            'name': 'LUSD Stablecoin',
            'chainId': 1,
            'version': '1',
            'verifyingContract': LUSD_ADDRESS,
        },
        'message': {
            'deadline': deadline,
            'nonce': nonce,
            'owner': user_address,
            'spender': spender_address,
            'value': amount_wei,
        },
        'primaryType': 'Permit',
        'types': {
            'EIP712Domain': [
                {'name': 'name', 'type': 'string'},
                {'name': 'version', 'type': 'string'},
                {'name': 'chainId', 'type': 'uint256'},
                {'name': 'verifyingContract', 'type': 'address'},
            ],
            'Permit': [
                {'name': 'owner', 'type': 'address'},
                {'name': 'spender', 'type': 'address'},
                {'name': 'value', 'type': 'uint256'},
                {'name': 'nonce', 'type': 'uint256'},
                {'name': 'deadline', 'type': 'uint256'},
            ]
        }
    }


def deposit_as_farm(user, amount, gamma_farm, pk=None, tx_args={}):
    pk = pk or get_test_account_pk(user.address)
    deadline = 1700000000
    permit_data = create_lusd_permit_data(user.address, gamma_farm.address, amount, deadline)
    permit_msg = eth_account.messages.encode_structured_data(permit_data)
    permit_signature = eth_account.Account.from_key(pk).sign_message(permit_msg)
    permit_signature_hex = permit_signature.signature.hex()
    r = permit_signature_hex[0:66]
    s = '0x' + permit_signature_hex[66:130]
    v = permit_signature.v
    tx = gamma_farm.depositAsFarm(amount, deadline, v, r, s, {'from': user} | tx_args)
    return tx


def deposit(user, amount, gamma_farm, pk=None, tx_args={}):
    pk = pk or get_test_account_pk(user.address)
    deadline = 1700000000
    permit_data = create_lusd_permit_data(user.address, gamma_farm.address, amount, deadline)
    permit_msg = eth_account.messages.encode_structured_data(permit_data)
    permit_signature = eth_account.Account.from_key(pk).sign_message(permit_msg)
    permit_signature_hex = permit_signature.signature.hex()
    r = permit_signature_hex[0:66]
    s = '0x' + permit_signature_hex[66:130]
    v = permit_signature.v
    tx = gamma_farm.deposit(amount, deadline, v, r, s, {'from': user} | tx_args)
    return tx


def get_test_account_pk(address):
    assert network.show_active() == "mainnet-fork"
    mnemonic = CONFIG.networks['mainnet-fork']['cmd_settings']['mnemonic']
    num_accounts = CONFIG.networks['mainnet-fork']['cmd_settings']['accounts']
    ETH_PATH_ROOT = "m/44'/60'/0'/0"
    seed = eth_account.account.seed_from_mnemonic(mnemonic, passphrase='')
    for account_index in range(num_accounts):
        account_path = ETH_PATH_ROOT + '/' + str(account_index)
        pk = eth_account.account.key_from_seed(seed, account_path)
        account = eth_account.account.Account.from_key(pk)
        if account.address == address:
            pk_hex = eth_account.account.HexBytes(pk).hex()
            return pk_hex
    raise Exception(f"unknown address {address}")


def simulate_liquidation(test_price_feed=None):
    trove_manager = Contract(LUSD_TROVE_MANAGER_ADDRESS)
    sorted_troves = Contract(LUSD_SORTED_TROVES_ADDRESS)
    price_feed = Contract(LUSD_PRICE_FEED_ADDRESS)
    # Calculate undercoll price:
    lowest_trove_address = sorted_troves.getLast()
    (lusd_debt, eth_coll, _, _, _) = trove_manager.Troves(lowest_trove_address)
    lusd_debt += trove_manager.getPendingLUSDDebtReward(lowest_trove_address)
    eth_coll += trove_manager.getPendingETHReward(lowest_trove_address)
    undercoll_price = trove_manager.MCR() * lusd_debt // eth_coll
    # Deploy or get TestPriceFeed with undercoll price set:
    test_price_feed = test_price_feed or (TestPriceFeed[-1] if len(TestPriceFeed) else None)
    if test_price_feed is None:
        test_price_feed = deploy_test_price_feed(undercoll_price)
    else:
        test_price_feed.setPrice(undercoll_price)
    # Replace PriceFeed and simulate liquidation:
    replace_price_feed(trove_manager, test_price_feed)
    trove_manager.liquidateTroves(1, {'from': accounts[0]})
    replace_price_feed(trove_manager, price_feed)


def replace_price_feed(trove_manager, custom_price_feed):
    trove_manager.setAddresses(
        trove_manager.borrowerOperationsAddress.call(),
        trove_manager.activePool.call(),
        trove_manager.defaultPool.call(),
        trove_manager.stabilityPool.call(),
        LUSD_GAS_POOL_ADDRESS,
        LUSD_COLL_SURPLUS_ADDRESS,
        custom_price_feed.address,
        trove_manager.lusdToken.call(),
        trove_manager.sortedTroves.call(),
        trove_manager.lqtyToken.call(),
        trove_manager.lqtyStaking.call(),
        {'from': ZERO_ADDRESS},
    )


# Returns a^n for 18-digit decimal base "a" and integer "n"
def dec_pow(a, n):
    def dec_mul(x, y):
        return (x * y + E18 // 2) // E18
    if n == 0:
        return E18
    y = E18
    x = a
    while n > 1:
        if n % 2 == 0:
            x = dec_mul(x, x)
            n = n // 2
        else:
            y = dec_mul(x, y)
            x = dec_mul(x, x)
            n = (n - 1) // 2
    return dec_mul(x, y)


# Estimate R and F parameters, given Q, T, Q1, T1, eT for reward distribution:
#   q(n) := R * eT * (1 - F^n) / (1 - F),
# where:
# - q(n) is total amount of tokens rewarded after n full epochs
# - target to distribute "Q" tokens over the period of "T" seconds
# - target to distribute "Q1" tokens within the first "T1" seconds
# - "R" tokens are initially distributed per second
# - "eT" is epoch duration seconds
# - "F^n" is approximated by dec_pow(F, n)
# - "R" decays every epoch with ~approx "F" factor
def estimate_rate_decay_params(Q, T, Q1, T1, eT):
    assert Q1 < Q and T1 < T
    assert T1 % eT == 0 and T % eT == 0
    (n, N) = (T1 // eT, T // eT)  # epochs in T1 and T
    # Find F:
    # (1 - F^n) / (1 - F^N) ~ Q1 / Q
    (f1, f2) = (1, E18 - 1)
    min_rel = (E18 - dec_pow(f2, n)) / (E18 - dec_pow(f2, N))
    max_rel = (E18 - dec_pow(f1, n)) / (E18 - dec_pow(f1, N))
    assert min_rel <= Q1 / Q <= max_rel
    while f2 - f1 >= 1:
        f = f1 + (f2 - f1 + 1) // 2
        (fq, fq1) = (E18 - dec_pow(f, N), E18 - dec_pow(f, n))
        (f1, f2) = (f1, f - 1) if fq * Q1 > fq1 * Q else (f, f2)
    F = f1
    # Find R:
    (r1, r2) = (1, Q)
    while r2 - r1 >= 1:
        r = r1 + (r2 - r1 + 1) // 2
        q = calculate_rate_decay_reward(r, F, eT, T)
        (r1, r2) = (r1, r - 1) if q > Q else (r, r2)
    R = r1
    return (R, F)


# Calculate total tokens rewarded after "t" seconds for reward distribution:
#   q(n) := R * eT * (1 - F^n) / (1 - F),
# where:
# - q(n) is total amount of tokens rewarded after n full epochs
# - "R" tokens are initially distributed per second
# - "eT" is epoch duration seconds
# - "F^n" is approximated by dec_pow(F, n)
# - "R" decays every epoch with ~approx "F" factor
def calculate_rate_decay_reward(R, F, eT, t):
    if F == E18:
        return R * t
    n = t // eT
    f_pow = dec_pow(F, n)
    (fa, fb) = (E18 - f_pow, E18 - F)
    cum_f = fa * E18 // fb
    return (R * cum_f * eT // E18) + (R * f_pow * (t - n * eT) // E18)


def print_console_logs(tx):
    for v in get_console_logs(tx):
        print(v)


def get_console_logs(tx):
    from web3 import Web3
    from eth_abi import decode_abi
    logs = []
    for subcall in tx.subcalls:
        if subcall['to'] != '0x000000000000000000636F6e736F6c652e6c6f67':
            continue
        call_sighash = subcall['calldata'][2:10]
        if call_sighash not in CONSOLE_LOG_TYPES_BY_SIGHASH:
            continue
        call_input = Web3.toBytes(hexstr=subcall['calldata'][10:])
        v = decode_abi(CONSOLE_LOG_TYPES_BY_SIGHASH[call_sighash], call_input)
        logs.append(v)
    return logs


CONSOLE_LOG_TYPES_BY_SIGHASH = {
    "51973ec9": [''],
    "4e0c1d1d": ['int'],
    "f5b1bba9": ['uint'],
    "41304fac": ['string'],
    "32458eed": ['bool'],
    "2c2ecbc2": ['address'],
    "0be77f56": ['bytes'],
    "ca82bb81": ['byte'],
    "6e18a128": ['bytes1'],
    "e9b62296": ['bytes2'],
    "2d834926": ['bytes3'],
    "e05f48d1": ['bytes4'],
    "a684808d": ['bytes5'],
    "ae84a591": ['bytes6'],
    "4ed57e28": ['bytes7'],
    "4f84252e": ['bytes8'],
    "90bd8cd0": ['bytes9'],
    "013d178b": ['bytes10'],
    "04004a2e": ['bytes11'],
    "86a06abd": ['bytes12'],
    "94529e34": ['bytes13'],
    "9266f07f": ['bytes14'],
    "da9574e0": ['bytes15'],
    "665c6104": ['bytes16'],
    "339f673a": ['bytes17'],
    "c4d23d9a": ['bytes18'],
    "5e6b5a33": ['bytes19'],
    "5188e3e9": ['bytes20'],
    "e9da3560": ['bytes21'],
    "d5fae89c": ['bytes22'],
    "aba1cf0d": ['bytes23'],
    "f1b35b34": ['bytes24'],
    "0b84bc58": ['bytes25'],
    "f8b149f1": ['bytes26'],
    "3a3757dd": ['bytes27'],
    "c82aeaee": ['bytes28'],
    "4b69c3d5": ['bytes29'],
    "ee12c4ed": ['bytes30'],
    "c2854d92": ['bytes31'],
    "27b7cf85": ['bytes32'],
    "6c0f6980": ['uint', 'uint'],
    "0fa3f345": ['uint', 'string'],
    "1e6dd4ec": ['uint', 'bool'],
    "58eb860c": ['uint', 'address'],
    "9710a9d0": ['string', 'uint'],
    "4b5c4277": ['string', 'string'],
    "c3b55635": ['string', 'bool'],
    "319af333": ['string', 'address'],
    "364b6a92": ['bool', 'uint'],
    "8feac525": ['bool', 'string'],
    "2a110e83": ['bool', 'bool'],
    "853c4849": ['bool', 'address'],
    "2243cfa3": ['address', 'uint'],
    "759f86bb": ['address', 'string'],
    "75b605d3": ['address', 'bool'],
    "daf0d4aa": ['address', 'address'],
    "e7820a74": ['uint', 'uint', 'uint'],
    "7d690ee6": ['uint', 'uint', 'string'],
    "67570ff7": ['uint', 'uint', 'bool'],
    "be33491b": ['uint', 'uint', 'address'],
    "5b6de83f": ['uint', 'string', 'uint'],
    "3f57c295": ['uint', 'string', 'string'],
    "46a7d0ce": ['uint', 'string', 'bool'],
    "1f90f24a": ['uint', 'string', 'address'],
    "5a4d9922": ['uint', 'bool', 'uint'],
    "8b0e14fe": ['uint', 'bool', 'string'],
    "d5ceace0": ['uint', 'bool', 'bool'],
    "424effbf": ['uint', 'bool', 'address'],
    "884343aa": ['uint', 'address', 'uint'],
    "ce83047b": ['uint', 'address', 'string'],
    "7ad0128e": ['uint', 'address', 'bool'],
    "7d77a61b": ['uint', 'address', 'address'],
    "969cdd03": ['string', 'uint', 'uint'],
    "a3f5c739": ['string', 'uint', 'string'],
    "f102ee05": ['string', 'uint', 'bool'],
    "e3849f79": ['string', 'uint', 'address'],
    "f362ca59": ['string', 'string', 'uint'],
    "2ced7cef": ['string', 'string', 'string'],
    "b0e0f9b5": ['string', 'string', 'bool'],
    "95ed0195": ['string', 'string', 'address'],
    "291bb9d0": ['string', 'bool', 'uint'],
    "e298f47d": ['string', 'bool', 'string'],
    "850b7ad6": ['string', 'bool', 'bool'],
    "932bbb38": ['string', 'bool', 'address'],
    "07c81217": ['string', 'address', 'uint'],
    "e0e9ad4f": ['string', 'address', 'string'],
    "c91d5ed4": ['string', 'address', 'bool'],
    "fcec75e0": ['string', 'address', 'address'],
    "3b5c03e0": ['bool', 'uint', 'uint'],
    "c8397eb0": ['bool', 'uint', 'string'],
    "1badc9eb": ['bool', 'uint', 'bool'],
    "c4d23507": ['bool', 'uint', 'address'],
    "c0382aac": ['bool', 'string', 'uint'],
    "b076847f": ['bool', 'string', 'string'],
    "dbb4c247": ['bool', 'string', 'bool'],
    "9591b953": ['bool', 'string', 'address'],
    "b01365bb": ['bool', 'bool', 'uint'],
    "2555fa46": ['bool', 'bool', 'string'],
    "50709698": ['bool', 'bool', 'bool'],
    "1078f68d": ['bool', 'bool', 'address'],
    "eb704baf": ['bool', 'address', 'uint'],
    "de9a9270": ['bool', 'address', 'string'],
    "18c9c746": ['bool', 'address', 'bool'],
    "d2763667": ['bool', 'address', 'address'],
    "8786135e": ['address', 'uint', 'uint'],
    "baf96849": ['address', 'uint', 'string'],
    "e54ae144": ['address', 'uint', 'bool'],
    "97eca394": ['address', 'uint', 'address'],
    "1cdaf28a": ['address', 'string', 'uint'],
    "fb772265": ['address', 'string', 'string'],
    "cf020fb1": ['address', 'string', 'bool'],
    "f08744e8": ['address', 'string', 'address'],
    "2c468d15": ['address', 'bool', 'uint'],
    "212255cc": ['address', 'bool', 'string'],
    "eb830c92": ['address', 'bool', 'bool'],
    "f11699ed": ['address', 'bool', 'address'],
    "6c366d72": ['address', 'address', 'uint'],
    "007150be": ['address', 'address', 'string'],
    "f2a66286": ['address', 'address', 'bool'],
    "018c84c2": ['address', 'address', 'address'],
    "5ca0ad3e": ['uint', 'uint', 'uint', 'uint'],
    "78ad7a0c": ['uint', 'uint', 'uint', 'string'],
    "6452b9cb": ['uint', 'uint', 'uint', 'bool'],
    "e0853f69": ['uint', 'uint', 'uint', 'address'],
    "3894163d": ['uint', 'uint', 'string', 'uint'],
    "7c032a32": ['uint', 'uint', 'string', 'string'],
    "b22eaf06": ['uint', 'uint', 'string', 'bool'],
    "433285a2": ['uint', 'uint', 'string', 'address'],
    "6c647c8c": ['uint', 'uint', 'bool', 'uint'],
    "efd9cbee": ['uint', 'uint', 'bool', 'string'],
    "94be3bb1": ['uint', 'uint', 'bool', 'bool'],
    "e117744f": ['uint', 'uint', 'bool', 'address'],
    "610ba8c0": ['uint', 'uint', 'address', 'uint'],
    "d6a2d1de": ['uint', 'uint', 'address', 'string'],
    "a8e820ae": ['uint', 'uint', 'address', 'bool'],
    "ca939b20": ['uint', 'uint', 'address', 'address'],
    "c0043807": ['uint', 'string', 'uint', 'uint'],
    "a2bc0c99": ['uint', 'string', 'uint', 'string'],
    "875a6e2e": ['uint', 'string', 'uint', 'bool'],
    "ab7bd9fd": ['uint', 'string', 'uint', 'address'],
    "76ec635e": ['uint', 'string', 'string', 'uint'],
    "57dd0a11": ['uint', 'string', 'string', 'string'],
    "12862b98": ['uint', 'string', 'string', 'bool'],
    "cc988aa0": ['uint', 'string', 'string', 'address'],
    "a4b48a7f": ['uint', 'string', 'bool', 'uint'],
    "8d489ca0": ['uint', 'string', 'bool', 'string'],
    "51bc2bc1": ['uint', 'string', 'bool', 'bool'],
    "796f28a0": ['uint', 'string', 'bool', 'address'],
    "98e7f3f3": ['uint', 'string', 'address', 'uint'],
    "f898577f": ['uint', 'string', 'address', 'string'],
    "f93fff37": ['uint', 'string', 'address', 'bool'],
    "7fa5458b": ['uint', 'string', 'address', 'address'],
    "56828da4": ['uint', 'bool', 'uint', 'uint'],
    "e8ddbc56": ['uint', 'bool', 'uint', 'string'],
    "d2abc4fd": ['uint', 'bool', 'uint', 'bool'],
    "4f40058e": ['uint', 'bool', 'uint', 'address'],
    "915fdb28": ['uint', 'bool', 'string', 'uint'],
    "a433fcfd": ['uint', 'bool', 'string', 'string'],
    "346eb8c7": ['uint', 'bool', 'string', 'bool'],
    "496e2bb4": ['uint', 'bool', 'string', 'address'],
    "bd25ad59": ['uint', 'bool', 'bool', 'uint'],
    "318ae59b": ['uint', 'bool', 'bool', 'string'],
    "4e6c5315": ['uint', 'bool', 'bool', 'bool'],
    "5306225d": ['uint', 'bool', 'bool', 'address'],
    "41b5ef3b": ['uint', 'bool', 'address', 'uint'],
    "a230761e": ['uint', 'bool', 'address', 'string'],
    "91fb1242": ['uint', 'bool', 'address', 'bool'],
    "86edc10c": ['uint', 'bool', 'address', 'address'],
    "ca9a3eb4": ['uint', 'address', 'uint', 'uint'],
    "3ed3bd28": ['uint', 'address', 'uint', 'string'],
    "19f67369": ['uint', 'address', 'uint', 'bool'],
    "fdb2ecd4": ['uint', 'address', 'uint', 'address'],
    "a0c414e8": ['uint', 'address', 'string', 'uint'],
    "8d778624": ['uint', 'address', 'string', 'string'],
    "22a479a6": ['uint', 'address', 'string', 'bool'],
    "cbe58efd": ['uint', 'address', 'string', 'address'],
    "7b08e8eb": ['uint', 'address', 'bool', 'uint'],
    "63f0e242": ['uint', 'address', 'bool', 'string'],
    "7e27410d": ['uint', 'address', 'bool', 'bool'],
    "b6313094": ['uint', 'address', 'bool', 'address'],
    "9a3cbf96": ['uint', 'address', 'address', 'uint'],
    "7943dc66": ['uint', 'address', 'address', 'string'],
    "01550b04": ['uint', 'address', 'address', 'bool'],
    "554745f9": ['uint', 'address', 'address', 'address'],
    "08ee5666": ['string', 'uint', 'uint', 'uint'],
    "a54ed4bd": ['string', 'uint', 'uint', 'string'],
    "f73c7e3d": ['string', 'uint', 'uint', 'bool'],
    "bed728bf": ['string', 'uint', 'uint', 'address'],
    "a0c4b225": ['string', 'uint', 'string', 'uint'],
    "6c98dae2": ['string', 'uint', 'string', 'string'],
    "e99f82cf": ['string', 'uint', 'string', 'bool'],
    "bb7235e9": ['string', 'uint', 'string', 'address'],
    "550e6ef5": ['string', 'uint', 'bool', 'uint'],
    "76cc6064": ['string', 'uint', 'bool', 'string'],
    "e37ff3d0": ['string', 'uint', 'bool', 'bool'],
    "e5549d91": ['string', 'uint', 'bool', 'address'],
    "58497afe": ['string', 'uint', 'address', 'uint'],
    "3254c2e8": ['string', 'uint', 'address', 'string'],
    "1106a8f7": ['string', 'uint', 'address', 'bool'],
    "eac89281": ['string', 'uint', 'address', 'address'],
    "d5cf17d0": ['string', 'string', 'uint', 'uint'],
    "8d142cdd": ['string', 'string', 'uint', 'string'],
    "e65658ca": ['string', 'string', 'uint', 'bool'],
    "5d4f4680": ['string', 'string', 'uint', 'address'],
    "9fd009f5": ['string', 'string', 'string', 'uint'],
    "de68f20a": ['string', 'string', 'string', 'string'],
    "2c1754ed": ['string', 'string', 'string', 'bool'],
    "6d572f44": ['string', 'string', 'string', 'address'],
    "86818a7a": ['string', 'string', 'bool', 'uint'],
    "5e84b0ea": ['string', 'string', 'bool', 'string'],
    "40785869": ['string', 'string', 'bool', 'bool'],
    "c371c7db": ['string', 'string', 'bool', 'address'],
    "4a81a56a": ['string', 'string', 'address', 'uint'],
    "eb1bff80": ['string', 'string', 'address', 'string'],
    "5ccd4e37": ['string', 'string', 'address', 'bool'],
    "439c7bef": ['string', 'string', 'address', 'address'],
    "5dbff038": ['string', 'bool', 'uint', 'uint'],
    "42b9a227": ['string', 'bool', 'uint', 'string'],
    "3cc5b5d3": ['string', 'bool', 'uint', 'bool'],
    "71d3850d": ['string', 'bool', 'uint', 'address'],
    "34cb308d": ['string', 'bool', 'string', 'uint'],
    "a826caeb": ['string', 'bool', 'string', 'string'],
    "3f8a701d": ['string', 'bool', 'string', 'bool'],
    "e0625b29": ['string', 'bool', 'string', 'address'],
    "807531e8": ['string', 'bool', 'bool', 'uint'],
    "9d22d5dd": ['string', 'bool', 'bool', 'string'],
    "895af8c5": ['string', 'bool', 'bool', 'bool'],
    "7190a529": ['string', 'bool', 'bool', 'address'],
    "28df4e96": ['string', 'bool', 'address', 'uint'],
    "2d8e33a4": ['string', 'bool', 'address', 'string'],
    "958c28c6": ['string', 'bool', 'address', 'bool'],
    "33e9dd1d": ['string', 'bool', 'address', 'address'],
    "daa394bd": ['string', 'address', 'uint', 'uint'],
    "4c55f234": ['string', 'address', 'uint', 'string'],
    "5ac1c13c": ['string', 'address', 'uint', 'bool'],
    "a366ec80": ['string', 'address', 'uint', 'address'],
    "8f624be9": ['string', 'address', 'string', 'uint'],
    "245986f2": ['string', 'address', 'string', 'string'],
    "5f15d28c": ['string', 'address', 'string', 'bool'],
    "aabc9a31": ['string', 'address', 'string', 'address'],
    "c5d1bb8b": ['string', 'address', 'bool', 'uint'],
    "0454c079": ['string', 'address', 'bool', 'string'],
    "79884c2b": ['string', 'address', 'bool', 'bool'],
    "223603bd": ['string', 'address', 'bool', 'address'],
    "6eb7943d": ['string', 'address', 'address', 'uint'],
    "800a1c67": ['string', 'address', 'address', 'string'],
    "b59dbd60": ['string', 'address', 'address', 'bool'],
    "ed8f28f6": ['string', 'address', 'address', 'address'],
    "32dfa524": ['bool', 'uint', 'uint', 'uint'],
    "da0666c8": ['bool', 'uint', 'uint', 'string'],
    "a41d81de": ['bool', 'uint', 'uint', 'bool'],
    "f161b221": ['bool', 'uint', 'uint', 'address'],
    "4180011b": ['bool', 'uint', 'string', 'uint'],
    "d32a6548": ['bool', 'uint', 'string', 'string'],
    "91d2f813": ['bool', 'uint', 'string', 'bool'],
    "a5c70d29": ['bool', 'uint', 'string', 'address'],
    "d3de5593": ['bool', 'uint', 'bool', 'uint'],
    "b6d569d4": ['bool', 'uint', 'bool', 'string'],
    "9e01f741": ['bool', 'uint', 'bool', 'bool'],
    "4267c7f8": ['bool', 'uint', 'bool', 'address'],
    "caa5236a": ['bool', 'uint', 'address', 'uint'],
    "18091341": ['bool', 'uint', 'address', 'string'],
    "65adf408": ['bool', 'uint', 'address', 'bool'],
    "8a2f90aa": ['bool', 'uint', 'address', 'address'],
    "8e4ae86e": ['bool', 'string', 'uint', 'uint'],
    "77a1abed": ['bool', 'string', 'uint', 'string'],
    "20bbc9af": ['bool', 'string', 'uint', 'bool'],
    "5b22b938": ['bool', 'string', 'uint', 'address'],
    "5ddb2592": ['bool', 'string', 'string', 'uint'],
    "1762e32a": ['bool', 'string', 'string', 'string'],
    "1e4b87e5": ['bool', 'string', 'string', 'bool'],
    "97d394d8": ['bool', 'string', 'string', 'address'],
    "8d6f9ca5": ['bool', 'string', 'bool', 'uint'],
    "483d0416": ['bool', 'string', 'bool', 'string'],
    "dc5e935b": ['bool', 'string', 'bool', 'bool'],
    "538e06ab": ['bool', 'string', 'bool', 'address'],
    "1b0b955b": ['bool', 'string', 'address', 'uint'],
    "12d6c788": ['bool', 'string', 'address', 'string'],
    "6dd434ca": ['bool', 'string', 'address', 'bool'],
    "2b2b18dc": ['bool', 'string', 'address', 'address'],
    "4667de8e": ['bool', 'bool', 'uint', 'uint'],
    "50618937": ['bool', 'bool', 'uint', 'string'],
    "ab5cc1c4": ['bool', 'bool', 'uint', 'bool'],
    "0bff950d": ['bool', 'bool', 'uint', 'address'],
    "178b4685": ['bool', 'bool', 'string', 'uint'],
    "6d1e8751": ['bool', 'bool', 'string', 'string'],
    "b857163a": ['bool', 'bool', 'string', 'bool'],
    "f9ad2b89": ['bool', 'bool', 'string', 'address'],
    "c248834d": ['bool', 'bool', 'bool', 'uint'],
    "2ae408d4": ['bool', 'bool', 'bool', 'string'],
    "3b2a5ce0": ['bool', 'bool', 'bool', 'bool'],
    "8c329b1a": ['bool', 'bool', 'bool', 'address'],
    "609386e7": ['bool', 'bool', 'address', 'uint'],
    "a0a47963": ['bool', 'bool', 'address', 'string'],
    "c0a302d8": ['bool', 'bool', 'address', 'bool'],
    "f4880ea4": ['bool', 'bool', 'address', 'address'],
    "9bfe72bc": ['bool', 'address', 'uint', 'uint'],
    "a0685833": ['bool', 'address', 'uint', 'string'],
    "ee8d8672": ['bool', 'address', 'uint', 'bool'],
    "68f158b5": ['bool', 'address', 'uint', 'address'],
    "0b99fc22": ['bool', 'address', 'string', 'uint'],
    "a73c1db6": ['bool', 'address', 'string', 'string'],
    "e2bfd60b": ['bool', 'address', 'string', 'bool'],
    "6f7c603e": ['bool', 'address', 'string', 'address'],
    "4cb60fd1": ['bool', 'address', 'bool', 'uint'],
    "4a66cb34": ['bool', 'address', 'bool', 'string'],
    "6a9c478b": ['bool', 'address', 'bool', 'bool'],
    "1c41a336": ['bool', 'address', 'bool', 'address'],
}