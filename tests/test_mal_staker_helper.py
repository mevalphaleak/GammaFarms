from brownie import accounts, Contract
from scripts.setup import setup_v3_staking


def test_mal_staker_helper():
    [v3_staker, nft_manager] = setup_v3_staking()
    helper = Contract('0xcf1451Ed34b28913140F8748888aCC68dCCcc053')
    user = accounts[0]
    [a, b, c, d] = helper.findAllValidPositions(user)


# "brownie test tests/test_mal_staker_helper.py"