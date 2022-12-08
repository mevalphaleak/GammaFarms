from brownie import accounts, GammaFarm
from scripts.common import deposit, DAY_SECS, E18, estimate_rate_decay_params
from scripts.tokens import fund_lusd, fund_mal, USDC_ADDRESS
from eth_abi import encode_abi

REF_DEPOSIT_TX_GAS_USED = 165997
REF_UNSTAKE_TX_GAS_USED = 74902
REF_WITHDRAW_TX_GAS_USED = 134881
REF_CLAIM_TX_GAS_USED = 111594
REF_START_NEW_EPOCH_TX_GAS_USED = 1047139


def test_farm_operations_gas_limits(chain, owner):
    # Setup farm:
    mal_to_distribute = int(6000*E18)               # 6k MAL
    mal_distribution_period_secs = 4*365*DAY_SECS   # 4 years
    mal_decay_period_secs = DAY_SECS                # 1 day
    (mal_reward_per_sec, mal_decay_factor) = estimate_rate_decay_params(
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_to_distribute // 2,
        mal_distribution_period_secs // 4,
        mal_decay_period_secs,
    )
    gamma_farm = owner.deploy(
        GammaFarm,
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_reward_per_sec,
        mal_decay_factor,
        mal_decay_period_secs,
    )
    fund_mal(fund_to=gamma_farm.address, amount_wei=mal_to_distribute)
    # Sleep 365 decay periods to see the cost of calculating MAL reward:
    chain.sleep(365 * mal_decay_period_secs)
    trade_data = encode_abi(['address', 'uint24', 'bool'], [USDC_ADDRESS, 500, True])
    txs = {}
    # Fund users:
    users = accounts[0:4]
    [fund_lusd(fund_to=users[i], amount_wei=200*E18) for i in range(len(users))]
    # Epoch with initial deposit:
    chain.sleep(mal_decay_period_secs)
    txs['deposit0'] = deposit(users[0], 200*E18, gamma_farm)
    txs['epoch0'] = gamma_farm.startNewEpoch(trade_data, {'from': owner})
    # Epoch with no user actions (LQTY rewards only):
    chain.sleep(mal_decay_period_secs)
    txs['epoch1'] = gamma_farm.startNewEpoch(trade_data, {'from': owner})
    # Epoch with two deposits (LQTY rewards only):
    chain.sleep(mal_decay_period_secs)
    txs['deposit1'] = deposit(users[1], 200*E18, gamma_farm)
    chain.sleep(1)
    txs['deposit2'] = deposit(users[2], 100*E18, gamma_farm)
    chain.sleep(1)
    txs['epoch2'] = gamma_farm.startNewEpoch(trade_data, {'from': owner})
    # Epoch with no user actions (ETH + LQTY rewards):
    chain.sleep(mal_decay_period_secs)
    accounts[0].transfer(gamma_farm.address, int(0.1*E18))  # ETH reward
    txs['epoch3'] = gamma_farm.startNewEpoch(trade_data, {'from': owner})
    # Epoch with two unstakes and one deposit (ETH + LQTY rewards):
    chain.sleep(mal_decay_period_secs)
    txs['unstake1'] = gamma_farm.unstake({'from': users[1]})
    chain.sleep(1)
    txs['unstake2'] = gamma_farm.unstake({'from': users[2]})
    chain.sleep(1)
    txs['deposit3'] = deposit(users[3], 100*E18, gamma_farm)
    chain.sleep(1)
    accounts[0].transfer(gamma_farm.address, int(0.1*E18))  # ETH reward
    txs['epoch4'] = gamma_farm.startNewEpoch(trade_data, {'from': owner})
    # Emergency epoch with withdraws:
    chain.sleep(1)
    txs['withdraw1'] = gamma_farm.withdraw({'from': users[1]})
    chain.sleep(mal_decay_period_secs // 2)
    accounts[0].transfer(gamma_farm.address, int(0.1*E18))  # ETH reward
    txs['em_withdraw'] = gamma_farm.emergencyWithdraw(trade_data, {'from': owner})
    chain.sleep(mal_decay_period_secs // 2)
    txs['withdraw2'] = gamma_farm.withdraw({'from': users[2]})
    txs['em_recover'] = gamma_farm.emergencyRecover({'from': owner})
    # Claim:
    chain.sleep(mal_decay_period_secs)
    txs['claim'] = gamma_farm.claim({'from': users[3]})
    # Unstake and withdraw:
    chain.sleep(mal_decay_period_secs)
    txs['unstakeWith'] = gamma_farm.unstakeAndWithdraw({'from': users[3]})

    # Refernce tx limits:
    ref_tx_limits = {
        'deposit1': REF_DEPOSIT_TX_GAS_USED,        # (first op in epoch, new user, farm has funds in SP)
        'unstake1': REF_UNSTAKE_TX_GAS_USED,        # (first op in epoch)
        'withdraw1': REF_WITHDRAW_TX_GAS_USED,      # (first op in epoch, full withdraw)
        'claim': REF_CLAIM_TX_GAS_USED,             # (first op in epoch)
        'epoch4': REF_START_NEW_EPOCH_TX_GAS_USED,  # (epoch has deposit/unstake ops, LQTY/ETH rewards)
    }
    _save_to_file(txs, ref_tx_limits)

    # Checks to detect gas regressions:
    for tx_name in ref_tx_limits:
        assert txs[tx_name].gas_used <= 1.01 * ref_tx_limits[tx_name], f"{tx_name} regression detected"


def _save_to_file(txs, ref_tx_limits={}):
    with open('gas_perf.txt', 'w') as f:
        f.write(f"# ==== Gas used ====\n")
        for tx_name in txs:
            ref_str = ""
            if tx_name in ref_tx_limits:
                ref_tx_limit = ref_tx_limits[tx_name]
                delta = txs[tx_name].gas_used - ref_tx_limit
                delta_pct = 100 * (txs[tx_name].gas_used - ref_tx_limit) / ref_tx_limit
                ref_str = f" (delta={delta:+}, {delta_pct:+.4f}%)"
            f.write(f"# {tx_name:12}{txs[tx_name].gas_used}{ref_str}\n")


# ==== Gas used ====
# deposit0    176424
# epoch0      356677
# epoch1      983892
# deposit1    165997 (*)
# deposit2    153697
# epoch2      959800
# epoch3      974149
# unstake1    74902 (*)
# unstake2    74902
# deposit3    171222
# epoch4      1047139 (*)
# withdraw1   134881 (*)
# em_withdraw 964331
# withdraw2   122207
# em_recover  273349
# claim       111594 (*)
# unstakeWith 401991
