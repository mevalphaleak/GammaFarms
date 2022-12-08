from brownie import accounts, network, Contract
from brownie import GammaFarm
from brownie.network import chain, history
from brownie.network.transaction import TransactionReceipt as TxReceipt
from scripts.common import DAY_SECS, E18, E18d, UINT256_MAX
from scripts.common import deposit, estimate_rate_decay_params, print_console_logs, simulate_liquidation, LUSD_STABILITY_POOL_ADDRESS
from scripts.contracts import deploy_gamma_farm, NFT_POSITIONS_MANAGER_ADDRESS
from scripts.tokens import fund_lqty, fund_lusd, fund_mal, fund_weth, approve_lqty, approve_lusd, approve_mal, approve_weth
from scripts.tokens import LQTY_ADDRESS, LUSD_ADDRESS, MAL_ADDRESS, WETH_ADDRESS
from eth_abi import encode_abi
from sha3 import keccak_256
import time

MAL_UNISWAP_V3_STAKER_ADDRESS = "0x1f98407aaB862CdDeF78Ed252D6f557aA5b0f00d"
MAL_WETH_3000_POOL = "0x41506D56B16794e4F7F423AEFF366740D4bdd387"


def run_epochs(num=1):
    assert len(GammaFarm)
    gamma_farm = GammaFarm[-1]
    owner = accounts.at(gamma_farm.owner())
    for _ in range(num):
        chain.sleep(DAY_SECS)
        gamma_farm.startNewEpoch(b'', {'from': owner})


def setup_farming():
    owner = accounts[5]
    # Deploy and fund GammaFarm contract:
    mal_to_distribute = int(6000*E18)    # 6k MAL
    mal_distribution_period_secs = 4 * 365 * DAY_SECS   # 4 years
    mal_decay_period_secs = DAY_SECS
    (mal_reward_per_sec, mal_decay_factor) = estimate_rate_decay_params(
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_to_distribute // 2,
        mal_distribution_period_secs // 4,
        mal_decay_period_secs,
    )
    gamma_farm = deploy_gamma_farm(
        mal_to_distribute=mal_to_distribute,
        mal_distribution_period_secs=mal_distribution_period_secs,
        mal_reward_per_sec=mal_reward_per_sec,
        mal_decay_factor=mal_decay_factor,
        mal_decay_period_secs=mal_decay_period_secs,
        owner=owner,
    )
    fund_mal(fund_to=gamma_farm.address, amount_wei=mal_to_distribute)
    # Fund user with LUSD:
    fund_lusd(fund_to=accounts[0], amount_wei=1000*E18)
    return [gamma_farm, owner]


def setup_v3_staking():
    # Deploy staker contract and create incentive:
    v3_staker = Contract(MAL_UNISWAP_V3_STAKER_ADDRESS)
    fund_mal(fund_to=accounts[1])
    approve_mal(spender=v3_staker.address, tx_from=accounts[1])
    incentive_key = [
        MAL_ADDRESS,  # rewardToken
        MAL_WETH_3000_POOL,  # pool
        1631874458,  # startTime
        1694946458,  # endTime
        "0x90102a92e8E40561f88be66611E5437FEb339e79",  # refundee
    ]
    incentive_id = keccak_256(encode_abi(['address', 'address', 'uint256', 'uint256', 'address'], incentive_key)).hexdigest()
    # Fund user with tokens and create liquidity position:
    fund_mal(fund_to=accounts[0])
    fund_weth(fund_to=accounts[0])
    approve_mal(spender=NFT_POSITIONS_MANAGER_ADDRESS, tx_from=accounts[0])
    approve_weth(spender=NFT_POSITIONS_MANAGER_ADDRESS, tx_from=accounts[0])
    nft_manager = Contract(NFT_POSITIONS_MANAGER_ADDRESS)
    mint_tx = nft_manager.mint(
        [
            MAL_ADDRESS,  # token0
            WETH_ADDRESS,  # token1
            3000,  # fee
            -887220,  # tickLower
            887220,  # tickUpper
            int(100e18),  # amount0Desired
            int(0.0979e18),  # amount1Desired
            int(0),  # amount0Min
            int(0),  # amount1Min
            accounts[0],  # receipient
            int(time.time()) + 3600,  # deadline
        ],
        {'from': accounts[0]},
    )
    [token_id, liquidity, amount0, amount1] = mint_tx.return_value
    print(f'Added position: tokenID={token_id}, liquidity={liquidity}, amount0={amount0}, amount1={amount1}')
    return [v3_staker, nft_manager]


def mainnet_fork():
    assert(network.show_active() == 'mainnet-fork')
    user = accounts[0]
    # For GammaFarm testing:
    [gamma_farm, owner] = setup_farming()
    # For UniswapV3Staker testing:
    [v3_staker, nft_manager] = setup_v3_staking()
    # Contracts:
    lusd_sp = Contract(LUSD_STABILITY_POOL_ADDRESS)
    # deposit(user, 100*E18, gamma_farm)
    # run_epochs(5)
    print('\nMainnet-fork is initialized and running...')
    print(f'Nonce for the next {user} tx: {user.nonce}')
    # chain.sleep(DAY_SECS)
    # epoch_tx = gamma_farm.startNewEpoch(b'', {'from': owner})
    # emergency_withdraw_tx = gamma_farm.emergencyWithdraw(b'', {'from': owner})

