from brownie import accounts, reverts
from scripts.common import deposit, simulate_liquidation, DAY_SECS, E18, E18d, UINT256_MAX
from scripts.tokens import fund_lusd
import pytest


def test_deposit(gamma_farm, lusd, lusd_sp):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    # Check min deposit is 1 LUSD:
    with reverts("minimum deposit is 1 LUSD"):
        deposit(user, E18 - 1, gamma_farm)
    deposit(user, 200*E18, gamma_farm)
    (lusd_available, lusd_staked, _, lusd_to_stake, should_unstake) = gamma_farm.getAccountBalances(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert (lusd_available, lusd_staked, lusd_to_stake, should_unstake) == (200*E18, 0, 200*E18, False)
    assert (total_lusd, total_lusd_staked) == (200*E18, 0)
    assert lusd.balanceOf(user) == 0
    assert lusd.balanceOf(gamma_farm.address) == 200*E18
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 0


def test_withdraw(chain, gamma_farm, lusd, mal, lusd_sp):
    user1 = accounts[0]
    user2 = accounts[1]
    fund_lusd(fund_to=user1, amount_wei=100*E18)
    fund_lusd(fund_to=user2, amount_wei=200*E18)
    deposit(user1, 100*E18, gamma_farm)
    deposit(user2, 200*E18, gamma_farm)
    chain.sleep(DAY_SECS)
    gamma_farm.withdraw({'from': user1})  # full withdrawal
    (lusd_available1, lusd_staked1, _, lusd_to_stake1, should_unstake1) = gamma_farm.getAccountBalances(user1)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert (lusd_available1, lusd_staked1, lusd_to_stake1, should_unstake1) == (0, 0, 0, False)
    assert (total_lusd, total_lusd_staked) == (200*E18, 0)
    assert lusd.balanceOf(user1) == 100*E18
    assert lusd.balanceOf(gamma_farm.address) == 200*E18
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 0
    assert mal.balanceOf(user1) > 0
    with reverts("nothing to withdraw"):
        gamma_farm.withdraw({'from': user1})


def test_start_new_epoch(chain, owner, gamma_farm, lusd, lusd_sp):
    (init_epoch, init_epoch_start_time) = (gamma_farm.epoch(), gamma_farm.epochStartTime())
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    deposit(user, 200*E18, gamma_farm) 
    chain.sleep(DAY_SECS)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    (lusd_available, lusd_staked, _, lusd_to_stake, should_unstake) = gamma_farm.getAccountBalances(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert (lusd_available, lusd_staked, lusd_to_stake, should_unstake) == (0, 200*E18, 0, False)
    assert (total_lusd, total_lusd_staked) == (200*E18, 200*E18)
    assert lusd.balanceOf(gamma_farm.address) == 0
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 200*E18
    assert gamma_farm.epoch() == init_epoch + 1
    assert gamma_farm.epochStartTime() >= init_epoch_start_time + DAY_SECS


def test_unstake(chain, owner, gamma_farm, lusd, lusd_sp):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    deposit(user, 200*E18, gamma_farm)
    with reverts("nothing to unstake"):
        gamma_farm.unstake({'from': user})
    # Start new epoch to stake:
    chain.sleep(1)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    gamma_farm.unstake({'from': user})
    # Check balances after unstake request (before new epoch):
    (lusd_available, lusd_staked, _, lusd_to_stake, should_unstake) = gamma_farm.getAccountBalances(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert (lusd_available, lusd_staked, lusd_to_stake, should_unstake) == (0, 200*E18, 0, True)
    assert (total_lusd, total_lusd_staked) == (200*E18, 200*E18)
    assert lusd.balanceOf(gamma_farm.address) == 0
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 200*E18
    # Start new epoch to trigger actual unstake
    chain.sleep(DAY_SECS)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    # Check balances after unstake:
    (lusd_available, lusd_staked, _, lusd_to_stake, should_unstake) = gamma_farm.getAccountBalances(user)
    (total_lusd, total_lusd_staked) = gamma_farm.getTotalBalances()
    assert lusd_available > 200*E18  # expect some reward from trading LQTY
    assert (lusd_staked, lusd_to_stake, should_unstake) == (0, 0, False)
    assert total_lusd >= lusd_available  # TODO: check precision (total_lusd1 ~ lusd_available)
    assert total_lusd_staked == 0
    assert lusd.balanceOf(gamma_farm.address) >= 0  # TODO: check precision (lusd_balance ~ 0)
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 0


def test_unstake_and_withdraw(chain, owner, gamma_farm, lusd, lusd_sp):
    users = accounts[0:3]
    [fund_lusd(fund_to=users[i], amount_wei=(i+1)*100*E18) for i in range(len(users))]
    [deposit(users[i], (i+1)*100*E18, gamma_farm) for i in range(len(users))]
    chain.sleep(DAY_SECS)
    with reverts("nothing to unstake"):
        gamma_farm.unstakeAndWithdraw({'from': users[0]})
    # Start new epoch to stake:
    gamma_farm.startNewEpoch(b'', {'from': owner})
    chain.sleep(DAY_SECS)
    # user0 makes unstakeAndWithdraw:
    (_, lusd_staked_before, _, _, _) = gamma_farm.getAccountBalances(users[0])
    (total_lusd_before, total_lusd_staked_before) = gamma_farm.getTotalBalances()
    lusd_sp_staked_before = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    lusd_unstaked0 = gamma_farm.unstakeAndWithdraw({'from': users[0]}).return_value
    (_, lusd_staked_after, _, _, _) = gamma_farm.getAccountBalances(users[0])
    (total_lusd_after, total_lusd_staked_after) = gamma_farm.getTotalBalances()
    lusd_sp_staked_after = lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address)
    assert (lusd_staked_before, lusd_unstaked0, lusd_staked_after) == (100*E18, 100*E18, 0)
    assert total_lusd_after == total_lusd_before - lusd_unstaked0
    assert total_lusd_staked_after == total_lusd_staked_before - lusd_unstaked0
    assert lusd_sp_staked_after == lusd_sp_staked_before - lusd_unstaked0
    assert lusd.balanceOf(users[0]) == 100*E18
    # user1 requests lazy unstake:
    gamma_farm.unstake({'from': users[1]})
    # Simulate liquidation:
    simulate_liquidation()
    # user1, user2 make unstakeAndWithdraw:
    lusd_unstaked1 = gamma_farm.unstakeAndWithdraw({'from': users[1]}).return_value
    lusd_unstaked2 = gamma_farm.unstakeAndWithdraw({'from': users[2]}).return_value
    # Check that actual unstaked amount is less than full amount due to liquidation loss:
    assert lusd_unstaked1 < 200*E18
    assert lusd_unstaked2 < 300*E18


def test_claim(chain, mal, gamma_farm):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    deposit(user, 200*E18, gamma_farm)
    chain.sleep(DAY_SECS)
    gamma_farm.claim({'from': user})
    assert mal.balanceOf(user) > 0
    # Nothing to claim after withdraw:
    gamma_farm.withdraw({'from': user})
    with reverts("nothing to claim"):
        gamma_farm.claim({'from': user})


def test_emergency_withdraw_recover(chain, owner, gamma_farm, lusd, lusd_sp):
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    deposit(user, 200*E18, gamma_farm)
    chain.sleep(1)
    gamma_farm.startNewEpoch(b'', {'from': owner})
    epoch = gamma_farm.epoch()
    chain.sleep(DAY_SECS)
    # Emergency withdraw:
    emergency_withdraw_tx = gamma_farm.emergencyWithdraw(b'', {'from': owner})
    (lusd_avail1, lusd_staked1, _, lusd_to_stake1, should_unstake1) = gamma_farm.getAccountBalances(user)
    (total_lusd1, total_lusd_staked1) = gamma_farm.getTotalBalances()
    assert gamma_farm.isEmergencyState() == True
    assert gamma_farm.epoch() == epoch + 1
    assert lusd_avail1 > 200*E18
    assert (lusd_staked1, lusd_to_stake1, should_unstake1) == (0, lusd_avail1, False)
    assert total_lusd1 / E18d == pytest.approx(lusd_avail1 / E18d, abs=1e-15)
    assert total_lusd_staked1 == 0
    assert lusd.balanceOf(gamma_farm.address) >= lusd_avail1  # TODO: check precision (lusd_balance ~ lusd_avail1)
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == 0
    chain.sleep(DAY_SECS // 2)
    # Emergency recover:
    emergency_recover_tx = gamma_farm.emergencyRecover({'from': owner})
    (lusd_avail2, lusd_staked2, _, lusd_to_stake2, should_unstake2) = gamma_farm.getAccountBalances(user)
    (total_lusd2, total_lusd_staked2) = gamma_farm.getTotalBalances()
    assert gamma_farm.isEmergencyState() == False
    assert gamma_farm.epoch() == epoch + 1
    assert (lusd_avail2, lusd_staked2, lusd_to_stake2, should_unstake2) == (0, lusd_to_stake1, 0, False)
    assert total_lusd2 == total_lusd1
    assert total_lusd_staked2 == total_lusd2
    assert lusd.balanceOf(gamma_farm.address) == 0
    assert lusd_sp.getCompoundedLUSDDeposit(gamma_farm.address) == total_lusd2


def test_start_new_epoch_by_user(chain, owner, gamma_farm):
    max_gov_only_epoch_duration = gamma_farm.MAX_GOV_ONLY_EPOCH_DURATION_SECS()
    (init_epoch, init_epoch_start_time) = (gamma_farm.epoch(), gamma_farm.epochStartTime())
    user = accounts[0]
    fund_lusd(fund_to=user, amount_wei=200*E18)
    deposit(user, 200*E18, gamma_farm)
    chain.sleep(1)
    # Check only governance can start new epoch (if epoch duration below threshold):
    with reverts():
        gamma_farm.startNewEpoch(b'', {'from': user})
    # Check any user can start new epoch (if epoch duration is above threshold):
    chain.sleep(max_gov_only_epoch_duration)
    gamma_farm.startNewEpoch(b'', {'from': user})
    assert gamma_farm.epoch() == init_epoch + 1
    assert gamma_farm.epochStartTime() >= init_epoch_start_time + max_gov_only_epoch_duration
    assert gamma_farm.getTotalBalances()== (200*E18, 200*E18)