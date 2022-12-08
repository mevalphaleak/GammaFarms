from brownie import accounts
from brownie import TestGammaFarm, TestStabilityPool
from scripts.common import deposit, simulate_liquidation, DAY_SECS, E18, UINT256_MAX
from scripts.tokens import fund_lusd, fund_mal
import pytest

from eth_abi import encode_abi


def test_lusd_compounded_rewards_single_user(chain, owner, gamma_farm, lusd, lusd_sp):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=100*E18)
    deposit(user, 100*E18, gamma_farm)
    chain.sleep(1)
    # First epoch:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    (lusd_available1, lusd_staked1, _, _, _) = gamma_farm.getAccountBalances(user)
    (total_lusd1, total_lusd_staked1) = gamma_farm.getTotalBalances()
    sp_deposit1 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    # Second epoch:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    (lusd_available2, lusd_staked2, _, _, _) = gamma_farm.getAccountBalances(user)
    (total_lusd2, total_lusd_staked2) = gamma_farm.getTotalBalances()
    sp_deposit2 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    # Third epoch (unstake requests at the end):
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    (lusd_available3, lusd_staked3, _, _, _) = gamma_farm.getAccountBalances(user)
    (total_lusd3, total_lusd_staked3) = gamma_farm.getTotalBalances()
    sp_deposit3 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    gamma_farm.unstake({'from': user})
    # New epoch to trigger unstake; withdraw:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    gamma_farm.withdraw({'from': user})
    # Check in-between epoch staked amounts are growing:
    assert sp_deposit1 < sp_deposit2 < sp_deposit3
    assert total_lusd_staked1 < total_lusd_staked2 < total_lusd_staked3
    assert total_lusd1 < total_lusd2 < total_lusd3
    assert lusd_staked1 < lusd_staked2 < lusd_staked3
    assert lusd_available1 == 0 and lusd_available2 == 0 and lusd_available3 == 0
    # Check final balances:
    (lusd_available, lusd_staked, _, _, _) = gamma_farm.getAccountBalances(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert (lusd_available, lusd_staked) == (0, 0)
    assert 0 <= total_lusd < 1e3  # TODO: estimate residual
    assert 0 <= total_lusd_staked <= total_lusd
    assert lusd.balanceOf(user) > 100*E18
    assert lusd.balanceOf(gamma_farm.address) == total_lusd - total_lusd_staked
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == total_lusd_staked
    # Check partial product:
    (P, _, _) = gamma_farm.getLastSnapshot()
    est_total_lusd = sp_deposit1 * P // E18
    act_total_lusd = total_lusd + lusd.balanceOf(user)
    assert est_total_lusd == pytest.approx(act_total_lusd, rel=1e-17)


def test_lusd_compounded_rewards_multiple_users(chain, owner, gamma_farm, lusd, lusd_sp):
    # Funding and initial deposits:
    users = accounts[0:3]
    deposits = [400*E18, 200*E18, 200*E18]
    [fund_lusd(fund_to=users[i], amount_wei=deposits[i]) for i in range(len(users))]
    [deposit(users[i], deposits[i], gamma_farm) for i in range(len(users))]
    chain.sleep(1)
    # First epoch:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    user_staked1 = [gamma_farm.getAccountLUSDStaked(users[i]) for i in range(len(users))]
    (_, total_lusd_staked1) = gamma_farm.getTotalBalances()
    sp_deposit1 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    # Second epoch:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    user_staked2 = [gamma_farm.getAccountLUSDStaked(users[i]) for i in range(len(users))]
    (_, total_lusd_staked2) = gamma_farm.getTotalBalances()
    sp_deposit2 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    # Third epoch (unstake requests at the end):
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    user_staked3 = [gamma_farm.getAccountLUSDStaked(users[i]) for i in range(len(users))]
    (_, total_lusd_staked3) = gamma_farm.getTotalBalances()
    sp_deposit3 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    [gamma_farm.unstake({'from': users[i]}) for i in range(len(users))]
    # New epoch to trigger unstake; withdraw:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    [gamma_farm.withdraw({'from': users[i]}) for i in range(len(users))]
    # Check in-between epoch staked amounts are growing:
    assert sp_deposit1 < sp_deposit2 < sp_deposit3
    assert total_lusd_staked1 < total_lusd_staked2 < total_lusd_staked3
    for i in range(len(users)):
        assert user_staked1[i] < user_staked2[i] < user_staked3[i]
    # Check in-between epoch user staked amounts relative to each other:
    assert user_staked1[0] == 2 * user_staked1[1]
    assert user_staked2[0] == 2 * user_staked2[1]
    assert user_staked3[0] == 2 * user_staked3[1]
    assert user_staked1[1] == user_staked1[2]
    assert user_staked2[1] == user_staked2[2]
    assert user_staked3[1] == user_staked3[2]
    # Check final total balances:
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert 0 <= total_lusd < 1e4  # TODO: estimate residual
    assert 0 <= total_lusd_staked <= total_lusd
    assert lusd.balanceOf(gamma_farm.address) == total_lusd - total_lusd_staked
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == total_lusd_staked
    # Check final user balances:
    for i in range(len(users)):
        assert lusd.balanceOf(users[i]) > deposits[i]
    assert lusd.balanceOf(users[0]) == 2 * lusd.balanceOf(users[1])
    assert lusd.balanceOf(users[1]) == lusd.balanceOf(users[2])
    # Check partial product:
    (P, _, _) = gamma_farm.getLastSnapshot()
    est_total_lusd = sp_deposit1 * P // E18
    act_total_lusd = total_lusd + sum([lusd.balanceOf(users[i]) for i in range(len(users))])
    assert est_total_lusd == pytest.approx(act_total_lusd, rel=1e-17)


def test_lusd_balances_after_liquidation(chain, owner, gamma_farm, lusd_sp, test_price_feed):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=100*E18)
    deposit(user, 100*E18, gamma_farm)
    chain.sleep(1)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(1)
    sp_deposit1 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    # Simulate liquidation:
    simulate_liquidation(test_price_feed)
    sp_deposit2 = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    assert sp_deposit1 > sp_deposit2
    # Start new epoch:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    # Check balances:
    lusd_staked = gamma_farm.getAccountLUSDStaked(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert total_lusd > 0 and total_lusd_staked > 0
    assert total_lusd == total_lusd_staked
    assert 0 <= total_lusd_staked - lusd_staked < 1e2


def test_lusd_rewards_loss(chain, owner):
    # Deploy TestGammaFarm:
    mal_to_distribute = 6000 * E18          # 6k MAL
    mal_distribution_period_secs = 6000     # 6000 secs
    mal_reward_per_sec = mal_to_distribute // mal_distribution_period_secs  # 1 MAL/sec
    mal_decay_factor = E18
    mal_decay_period_secs = mal_distribution_period_secs
    test_lusd_sp = accounts[0].deploy(TestStabilityPool)
    gamma_farm = owner.deploy(
        TestGammaFarm,
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_reward_per_sec,
        mal_decay_factor,
        mal_decay_period_secs,
        test_lusd_sp.address,
    )
    fund_mal(fund_to=gamma_farm.address, amount_wei=mal_to_distribute)
    # Fund users:
    users = accounts[0:3]
    deposits = [400*E18, 200*E18, 200*E18]
    init_total_lusd = sum(deposits)
    [fund_lusd(fund_to=users[i], amount_wei=deposits[i]) for i in range(len(users))]
    # Deposit and start new epoch:
    [deposit(users[i], deposits[i], gamma_farm) for i in range(len(users))]
    chain.sleep(1)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(1000)
    # First and second user unstake request:
    gamma_farm.unstake({'from': users[0]})
    gamma_farm.unstake({'from': users[1]})
    # Simulate loss and start new epoch:
    (lusd_reward, sp_loss) = (200*E18, 600*E18)
    test_lusd_sp.setCompoundedLUSDDeposit(init_total_lusd - sp_loss)
    fund_lusd(fund_to=gamma_farm.address, amount_wei=lusd_reward)
    gamma_farm.startNewEpoch(encode_abi(['uint256'], [lusd_reward]), {'from': owner})
    # Check balances:
    for i in range(len(users)):
        (lusd_available, lusd_staked, _, _, _) = gamma_farm.getAccountBalances(users[i])
        assert lusd_available == (deposits[i] // 2 if i < 2 else 0)
        assert lusd_staked == (0 if i < 2 else deposits[i] // 2)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert total_lusd == init_total_lusd // 2
    assert total_lusd_staked == deposits[2] // 2


def test_lusd_full_loss_epoch(chain, owner):
    # Deploy TestGammaFarm:
    mal_to_distribute = 6000 * E18          # 6k MAL
    mal_distribution_period_secs = 6000     # 6000 secs
    mal_reward_per_sec = mal_to_distribute // mal_distribution_period_secs  # 1 MAL/sec
    mal_decay_factor = E18
    mal_decay_period_secs = mal_distribution_period_secs
    test_lusd_sp = accounts[0].deploy(TestStabilityPool)
    gamma_farm = owner.deploy(
        TestGammaFarm,
        mal_to_distribute,
        mal_distribution_period_secs,
        mal_reward_per_sec,
        mal_decay_factor,
        mal_decay_period_secs,
        test_lusd_sp.address,
    )
    fund_mal(fund_to=gamma_farm.address, amount_wei=mal_to_distribute)
    # Fund users:
    users = accounts[0:2]
    [fund_lusd(fund_to=users[i], amount_wei=100*E18) for i in range(len(users))]
    # First user deposits:
    deposit0_tx = deposit(users[0], 100*E18, gamma_farm)
    chain.sleep(1)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(1000)
    # Unlikely event when Stability Pool is exhausted (i.e. was used in full to offset liquidations)
    # and somehow we didn't get any rewards (e.g. badly frontran)
    test_lusd_sp.setCompoundedLUSDDeposit(0)
    full_loss_epoch_tx = gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(1000)
    (lusd_available0, lusd_staked0, mal_rewards0, _, _) = gamma_farm.getAccountBalances(users[0])
    assert (lusd_available0, lusd_staked0) == (0, 0)
    assert mal_rewards0 == (full_loss_epoch_tx.timestamp - deposit0_tx.timestamp) * mal_reward_per_sec
    # Second user deposits:
    deposit1_tx = deposit(users[1], 100*E18, gamma_farm)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(1000)
    lusd_epoch_reward = 10*E18
    fund_lusd(fund_to=gamma_farm.address, amount_wei=lusd_epoch_reward)
    epoch_tx = gamma_farm.startNewEpoch(encode_abi(['uint256'], [lusd_epoch_reward]), {'from': owner})
    # Check balances:
    (lusd_available0, lusd_staked0, mal_rewards0, _, _) = gamma_farm.getAccountBalances(users[0])
    (lusd_available1, lusd_staked1, mal_rewards1, _, _) = gamma_farm.getAccountBalances(users[1])
    assert (lusd_available0, lusd_staked0) == (0, 0)
    assert mal_rewards0 == (full_loss_epoch_tx.timestamp - deposit0_tx.timestamp) * mal_reward_per_sec
    assert lusd_available1 == 0
    assert lusd_staked1 == 100*E18 + lusd_epoch_reward
    assert mal_rewards1 == (epoch_tx.timestamp - deposit1_tx.timestamp) * mal_reward_per_sec
