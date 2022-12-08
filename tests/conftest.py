from brownie import accounts, Contract
from brownie import GammaFarm, TestPriceFeed
from eth_abi import encode_abi
from scripts.tokens import fund_mal, LUSD_ADDRESS, LQTY_ADDRESS, MAL_ADDRESS

import pytest

LUSD_PRICE_FEED_ADDRESS = "0x4c517D4e2C851CA76d7eC94B805269Df0f2201De"
LUSD_STABILITY_POOL_ADDRESS = "0x66017D22b0f8556afDd19FC67041899Eb65a21bb"
LUSD_SORTED_TROVES_ADDRESS = "0x8FdD3fbFEb32b28fb73555518f8b361bCeA741A6"
LUSD_TROVE_MANAGER_ADDRESS = "0xA39739EF8b0231DbFA0DcdA07d7e29faAbCf4bb2"



@pytest.fixture(autouse=True)
def isolation(fn_isolation):
    pass


@pytest.fixture
def owner(accounts):
    yield accounts[5]


@pytest.fixture
def gamma_farm(owner, GammaFarm):
    # Deploy and fund the farming contract:
    mal_to_distribute = int(6000*10**18)    # 6k MAL
    mal_distribution_period_secs = 30*24*60*60   # 30 days
    mal_reward_per_sec = mal_to_distribute // mal_distribution_period_secs
    mal_decay_factor = 10**18
    mal_decay_period_secs = mal_distribution_period_secs
    gamma_farm = owner.deploy(
        GammaFarm,
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_reward_per_sec,
        mal_decay_factor,
        mal_decay_period_secs,
    )
    fund_mal(fund_to=gamma_farm.address, amount_wei=mal_to_distribute)
    yield gamma_farm


@pytest.fixture
def lusd_sp():
    yield Contract(LUSD_STABILITY_POOL_ADDRESS)


@pytest.fixture
def price_feed():
    yield Contract(LUSD_PRICE_FEED_ADDRESS)


@pytest.fixture
def sorted_troves():
    yield Contract(LUSD_SORTED_TROVES_ADDRESS)


@pytest.fixture
def trove_manager():
    yield Contract(LUSD_TROVE_MANAGER_ADDRESS)


@pytest.fixture
def test_price_feed(price_feed):
    price = price_feed.fetchPrice({'from': accounts[0]}).return_value
    yield accounts[0].deploy(TestPriceFeed, price)


@pytest.fixture
def lusd():
    yield Contract(LUSD_ADDRESS)


@pytest.fixture
def lqty():
    yield Contract(LQTY_ADDRESS)


@pytest.fixture
def mal():
    yield Contract(MAL_ADDRESS)