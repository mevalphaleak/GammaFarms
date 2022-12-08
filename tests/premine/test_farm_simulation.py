from brownie._config import CONFIG
CONFIG.networks['mainnet-fork']['cmd_settings']['block_time'] = 10000
CONFIG.networks['mainnet-fork']['cmd_settings']['accounts'] = 100

from scripts.common import estimate_rate_decay_params, DAY_SECS, E18, UINT256_MAX
from scripts.simulation.gamma_farm import GammaFarmSimulator
from scripts.simulation.gamma_farm_py import GammaFarmPythonSimulator
from scripts.simulation.gamma_farm_naive import GammaFarmNaiveSimulator
from scripts.simulation.structs import Event, EventType, EpochData, SimulationState

from collections import defaultdict
from decimal import Decimal
import numpy as np
import random


def test_realistic_simulation_mini(chain, history):
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 6000 * E18              # mal_to_distribute (6k MAL)
    T = 4 * 365 * DAY_SECS      # mal_distribution_period_secs (4 years)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    num_epochs = 20
    (events, exact_state) = _generate_events(num_epochs, eT, Q, T, R, F)
    assert int(exact_state.farmLusdBalance) == 0
    assert int(exact_state.totalLusd) == 0
    assert int(exact_state.totalLusdStaked) == 0
    py_sim = GammaFarmPythonSimulator(Q, T, R, F)
    py_state = py_sim.simulate_events(events)
    assert 0 <= py_state.totalLusd < 1e7  # TODO: estimate residual
    assert 0 <= py_state.totalLusdStaked <= py_state.totalLusd
    py_state.equals(exact_state, lusd_abs=1e-11, mal_abs=1e-11, user_lusd_abs=1e-11, user_mal_abs=1e-11, snap_mal_abs=SimulationState.SKIP_COMPARISON)
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_realistic_simulation():
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 6000 * E18              # mal_to_distribute (6k MAL)
    T = 4 * 365 * DAY_SECS      # mal_distribution_period_secs (4 years)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    num_epochs = 2000
    (events, exact_state) = _generate_events(num_epochs, eT, Q, T, R, F)
    assert int(exact_state.totalLusd) == 0
    assert int(exact_state.totalLusdStaked) == 0
    assert int(exact_state.farmLusdBalance) == 0
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    assert 0 <= py_state.totalLusd < 1e16  # TODO: estimate residual
    assert 0 <= py_state.totalLusdStaked <= py_state.totalLusd
    assert py_state.equals(exact_state, lusd_abs=1e-2, mal_abs=1e-6, user_lusd_abs=1e-2, user_mal_abs=1e-6, snap_mal_abs=SimulationState.SKIP_COMPARISON)


def _generate_events(num_epochs, epochT, Q, T, R, F):
    random.seed(27)
    np.random.seed(27)
    events = []
    unstakers = defaultdict(lambda: set())
    withdrawers = defaultdict(lambda: set())
    epoch_start_ts = 0
    users = set()
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F)
    is_emergency = False
    for epoch in range(num_epochs):
        epoch_events = []
        epoch_duration_secs = int(np.random.normal(epochT, epochT // 24, 1)[0])
        next_epoch_start_ts = epoch_start_ts + epoch_duration_secs
        emergency_recover_ts = None
        if is_emergency:
            emergency_recover_ts = random.randint(epoch_start_ts + epoch_duration_secs // 2, next_epoch_start_ts - 1)
            epoch_events.append(Event(emergency_recover_ts, EventType.EMERGENCY_RECOVER))
        # Deposit:
        tosses = 1 + int(4 * (num_epochs - epoch - 1) / num_epochs) if epoch < num_epochs - 1 else 0
        num_depositors = np.random.binomial(tosses, 0.5 * pow(0.999, epoch))
        for j in range(num_depositors):
            num_users = len(users)
            is_new_user = (num_users == 0 or random.random() > 0.01)
            user = num_users if is_new_user else random.randint(0, num_users - 1)
            users.add(user)
            amount = int((np.random.pareto(1.0, 1)[0] + 1) * 1000*E18)
            event_ts = random.randint(epoch_start_ts, next_epoch_start_ts)
            epoch_events.append(Event(event_ts, EventType.DEPOSIT, amount, user=user))
            epoch_to_unstake = random.randint(epoch, num_epochs - 2)
            if epoch_to_unstake > epoch:
                unstakers[epoch_to_unstake].add(user)
            else:
                event_ts = random.randint(event_ts, next_epoch_start_ts)
                epoch_events.append(Event(event_ts, EventType.WITHDRAW, user=user))
        # Unstake:
        (_, total_lusd_staked) = exact_sim.get_total_balances()
        total_lusd_staked_left = total_lusd_staked
        for user in unstakers[epoch]:
            (lusd_available, lusd_staked, _, _, _) = exact_sim.get_account_balances(user)
            if (not is_emergency and lusd_staked == 0) or (lusd_staked + lusd_available == 0):
                continue
            event_ts = random.randint(epoch_start_ts, next_epoch_start_ts)
            last_unstake_withdraw_ts = epoch_start_ts
            if is_emergency and event_ts < emergency_recover_ts:
                epoch_events.append(Event(event_ts, EventType.WITHDRAW, user=user))
            elif is_emergency or random.random() < 0.6 or total_lusd_staked_left < lusd_staked:
                epoch_events.append(Event(event_ts, EventType.UNSTAKE, user=user))
                epoch_to_withdraw = random.randint(epoch + 1, min(epoch + 10, num_epochs - 1))
                withdrawers[epoch_to_withdraw].add(user)
            else:
                sf = 1 if random.random() < 0.6 else 1 / Decimal(np.random.pareto(100, 1)[0] + 1)
                lusd_sp_loss = int(total_lusd_staked_left * (1 - sf))
                total_lusd_staked_left -= lusd_staked * (total_lusd_staked_left - lusd_sp_loss) // total_lusd_staked_left
                total_lusd_staked_left -= lusd_sp_loss
                event_ts = random.randint(last_unstake_withdraw_ts, next_epoch_start_ts)
                last_unstake_withdraw_ts = event_ts
                epoch_events.append(Event(event_ts, EventType.UNSTAKE_AND_WITHDRAW, user=user, data=EpochData(reward=0, loss=lusd_sp_loss)))
        # Withdraw:
        for user in withdrawers[epoch]:
            (lusd_available, _, _, _, _) = exact_sim.get_account_balances(user)
            if lusd_available == 0:
                continue
            event_ts = random.randint(epoch_start_ts, next_epoch_start_ts)
            epoch_events.append(Event(event_ts, EventType.WITHDRAW, user=user))
        # Generate reward/loss:
        (lusd_reward, lusd_sp_loss) = (0, 0)
        if total_lusd_staked > 0:
            pf = Decimal(np.random.normal(1.005, 0.01, 1)[0])
            sf = 1 if random.random() < 0.6 else 1 / Decimal(np.random.pareto(100, 1)[0] + 1)
            total_lusd_staked_after_profit = int(pf * total_lusd_staked)
            total_lusd_staked_after_loss = min(int(sf * total_lusd_staked_left), total_lusd_staked_after_profit)
            lusd_reward = total_lusd_staked_after_profit - total_lusd_staked_after_loss
            lusd_sp_loss = int(total_lusd_staked_left) - total_lusd_staked_after_loss
        # New epoch:
        reward_data = EpochData(reward=lusd_reward, loss=lusd_sp_loss)
        is_emergency = epoch < num_epochs and random.random() < 0.01
        if is_emergency:
            epoch_events.append(Event(next_epoch_start_ts, EventType.EMERGENCY_WITHDRAW, data=reward_data))
        else:
            epoch_events.append(Event(next_epoch_start_ts, EventType.NEW_EPOCH, data=reward_data))
        # Sort and simulate events:
        epoch_events.sort(key=lambda x: x.ts)
        for e in epoch_events:
            exact_sim.simulate_event(e)
        epoch_start_ts = next_epoch_start_ts
        events += epoch_events
    return (events, exact_sim.gather_state())
