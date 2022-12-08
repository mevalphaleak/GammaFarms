from brownie._config import CONFIG
CONFIG.networks['mainnet-fork']['cmd_settings']['block_time'] = 10000
CONFIG.networks['mainnet-fork']['cmd_settings']['accounts'] = 100

from brownie import accounts, Contract, GammaFarm
from scripts.common import deposit, DAY_SECS, E18
from brownie.network.transaction import Status as TxStatus
from scripts.simulation.gamma_farm import PremineChainHelper
from scripts.tokens import LUSD_HOLDER, LQTY_ADDRESS, LQTY_HOLDER, WETH_ADDRESS

UNISWAP_V3_ROUTER2_ADDRESS = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"


def test_start_new_epoch_frontrun_protection(chain, history, owner, lusd, lqty):
    pch = PremineChainHelper(chain, history)
    Q = 6000*E18    # mal_to_distribute (6k MAL)
    T = 5*60        # mal_distribution_period_secs (5 mins)
    R = Q // T      # mal_reward_per_sec
    F = E18         # mal_decay_factor (1.0)
    eT = DAY_SECS
    gamma_farm = pch.deploy_contract(GammaFarm, args=[Q, T, R, F, eT], deployer=owner)
    # Fund users:
    user = accounts[0]
    trader = accounts[1]
    transfer1_tx = user.transfer(LUSD_HOLDER, 10*E18, required_confs=0)
    transfer2_tx = user.transfer(LQTY_HOLDER, 10*E18, required_confs=0)
    pch.mine_block([transfer1_tx, transfer2_tx])
    fund_lusd_tx = lusd.transfer(user, 100*E18, pch.tx_args({'from': LUSD_HOLDER}))
    fund_lqty_tx = lqty.transfer(trader, 1000*E18, pch.tx_args({'from': LQTY_HOLDER}))
    approve_lqty_tx = lqty.approve(UNISWAP_V3_ROUTER2_ADDRESS, 10**30, pch.tx_args({'from': trader}))
    pch.mine_block([fund_lusd_tx, fund_lqty_tx, approve_lqty_tx])
    # Deposit and start new epoch:
    chain.sleep(1)
    deposit_tx = deposit(user, 100*E18, gamma_farm, tx_args=pch.tx_args())
    epoch1_tx = gamma_farm.startNewEpoch(b'', pch.tx_args({'from': owner}))
    pch.mine_block([deposit_tx, epoch1_tx], check_order=True)
    # Sleep to enable user starting next epoch:
    chain.sleep(gamma_farm.MAX_GOV_ONLY_EPOCH_DURATION_SECS())
    # Make LQTY/WETH trade and mine it the same block:
    router = Contract(UNISWAP_V3_ROUTER2_ADDRESS)
    lqty_trade_args = (LQTY_ADDRESS, WETH_ADDRESS, 3000, trader.address, 1000*E18, 1, 0)
    lqty_trade_tx = router.exactInputSingle(lqty_trade_args, pch.tx_args({'from': trader}))
    epoch2_tx = gamma_farm.startNewEpoch(b'', pch.tx_args({'from': user}))
    # Check start new epoch will revert:
    pch.mine_block([lqty_trade_tx, epoch2_tx], check_order=True, allow_revert=True)
    assert epoch2_tx.status == TxStatus.Reverted
    assert epoch2_tx.revert_msg == "frontrun protection"