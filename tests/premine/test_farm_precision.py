from brownie._config import CONFIG
CONFIG.networks['mainnet-fork']['cmd_settings']['block_time'] = 10000
CONFIG.networks['mainnet-fork']['cmd_settings']['accounts'] = 100

from scripts.common import estimate_rate_decay_params, DAY_SECS, E18, E18d, UINT256_MAX
from scripts.simulation.gamma_farm_py import GammaFarmPythonSimulator
from scripts.simulation.gamma_farm_naive import GammaFarmNaiveSimulator
from scripts.simulation.structs import Event, EventType, EpochData, SimulationState

from decimal import Decimal
import numpy as np
import random


def test_precision_lusd_stake_residual():
    Q = 6000 * E18   # mal_to_distribute (6k MAL)
    T = 4 * 365      # mal_distribution_period_secs
    eT = 1
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    events = [
        Event(0, EventType.DEPOSIT, 100*E18, user=0),
        Event(10, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(20, EventType.NEW_EPOCH, data=EpochData(reward=569965796302359488)),
        Event(30, EventType.NEW_EPOCH, data=EpochData(reward=839622377489234304)),
        Event(40, EventType.NEW_EPOCH, data=EpochData(reward=2984747196711203841)),
        Event(40 + 1, EventType.UNSTAKE, user=0),
        Event(50, EventType.NEW_EPOCH, data=EpochData(reward=3002922694686246499)),
        Event(50 + 1, EventType.WITHDRAW, user=0),
        Event(60, EventType.NEW_EPOCH, data=EpochData(reward=0)),
    ]
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    # Expect a residual due to precision errors, but check it's small:
    assert 0 < py_state.totalLusd / E18d < 1e-15
    assert 0 < py_state.totalLusdStaked <= py_state.totalLusd
    # Check partial MAL sums:
    assert py_state.S1 > 1e15 and py_state.S2 > 1e15
    assert py_state.equals(exact_state, lusd_abs=1e-15, mal_abs=1e-14, user_lusd_abs=1e-15, user_mal_abs=1e-14, snap_mal_abs=SimulationState.SKIP_COMPARISON)
    # Check residual doesn't affect future users:
    events2 = [
        Event(60 + 2, EventType.DEPOSIT, E18, user=1),
        Event(70, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(70 + 1, EventType.DEPOSIT, 100*E18 - 1, user=2),
        Event(80, EventType.NEW_EPOCH, data=EpochData(reward=4)),
        Event(90, EventType.NEW_EPOCH, data=EpochData(reward=569965796302359488)),
        Event(100, EventType.NEW_EPOCH, data=EpochData(reward=839622377489234304)),
        Event(100 + 1, EventType.UNSTAKE, user=1),
        Event(100 + 2, EventType.UNSTAKE, user=2),
        Event(110, EventType.NEW_EPOCH, data=EpochData(reward=2984747196711203841)),
        Event(110 + 1, EventType.WITHDRAW, user=1),
        Event(110 + 2, EventType.WITHDRAW, user=2),
    ]
    exact_state2 = exact_sim.simulate_events(events2)
    py_state2 = py_sim.simulate_events(events2)
    assert py_state2.equals(exact_state2, lusd_abs=1e-15, mal_abs=1e-13, user_lusd_abs=1e-15, user_mal_abs=1e-13, snap_mal_abs=SimulationState.SKIP_COMPARISON)


def test_precision_normal():
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 6000 * E18              # mal_to_distribute (6k MAL)
    T = 4 * 365 * DAY_SECS      # mal_distribution_period_secs (4 years)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    # Build events:
    num_epochs = 1000
    events = _build_events(num_epochs, eT)
    # Run simulators:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    for i in py_state.users:
        assert py_state.userLusdOut[i] <= int(exact_state.userLusdOut[i])
    assert py_state.equals(exact_state, lusd_abs=1e-9, mal_abs=1e-9, user_lusd_abs=1e-11, user_mal_abs=1e-11)


def test_precision_after_big_loss():
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 6000 * E18              # mal_to_distribute (6k MAL)
    T = 4 * 365 * DAY_SECS      # mal_distribution_period_secs (4 years)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    # Build events:
    num_epochs = 1000
    def reward_loss_func(staked, epoch):
        if epoch == 200:
            return (0, staked - staked // 10000)
        return _gen_normal_reward_loss(staked)
    events = _build_events(num_epochs, eT, reward_loss_func)
    # Run simulators:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    for i in py_state.users:
        assert py_state.userLusdOut[i] <= int(exact_state.userLusdOut[i])
    assert py_state.equals(exact_state, lusd_abs=1e-6, mal_abs=1e-7, user_lusd_abs=1e-8, user_mal_abs=1e-9)


def test_precision_ups_and_downs():
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 6000 * E18              # mal_to_distribute (6k MAL)
    T = 4 * 365 * DAY_SECS      # mal_distribution_period_secs (4 years)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)
    # Build events:
    num_epochs = 500
    def reward_loss_func(staked, epoch):
        if staked == 0:
            return (0, 0)
        if epoch < 100:
            # Profitable epochs 1..99:
            # reward=S/10, loss=S/100, pf=1.09
            return (staked // 10, staked // 100)
        elif epoch < 300:
            # Unprofitable epochs 100..299:
            # reward=0, loss=S/100, pf=0.99
            return (0, staked // 100)
        elif epoch < 400:
            # Profitable epochs 300..399:
            # reward=S/100, loss=0, pf=1.01
            return (staked // 100, 0)
        else:
            # Break-even epochs 400..499:
            # reward=S/10, loss=S/10, pf=1
            return (staked // 10, staked // 10)
    events = _build_events(num_epochs, eT, reward_loss_func)
    # Run simulators:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    for i in py_state.users:
        assert py_state.userLusdOut[i] <= round(exact_state.userLusdOut[i])
    assert py_state.equals(exact_state, lusd_abs=1e-9, mal_abs=1e-9, user_lusd_abs=1e-10, user_mal_abs=1e-10)


def _build_events(num_epochs, epoch_duration_secs, reward_loss_func=None, deposit_func=None):
    random.seed(27)
    np.random.seed(27)
    reward_loss_func = reward_loss_func or (lambda s, _: _gen_normal_reward_loss(s))
    deposit_func = deposit_func or (lambda _: 100*E18)
    events = []
    total_lusd_staked = 0
    for i in range(num_epochs):
        (lusd_reward, lusd_sp_loss) = reward_loss_func(total_lusd_staked, i)
        epoch_data = EpochData(reward=lusd_reward, loss=lusd_sp_loss)
        if i < num_epochs - 1:
            lusd_deposit = deposit_func(i)
            events += [Event((i + 1) * epoch_duration_secs, EventType.DEPOSIT, lusd_deposit, user=i)]
            total_lusd_staked = total_lusd_staked - lusd_sp_loss + lusd_reward + lusd_deposit
        else:
            for j in range(num_epochs - 1):
                events += [Event(num_epochs * epoch_duration_secs, EventType.UNSTAKE, user=j)]
        events += [Event((i + 1) * epoch_duration_secs, EventType.NEW_EPOCH, data=epoch_data)]
    for i in range(num_epochs - 1):
        events += [Event(num_epochs * epoch_duration_secs, EventType.WITHDRAW, user=i)]
    return events


def _gen_normal_reward_loss(total_lusd_staked):
    if total_lusd_staked == 0:
        return (0, 0)
    pf = Decimal(np.random.normal(1.005, 0.01, 1)[0])
    loss_f = Decimal(random.random())
    sf = min(1, pf) - (loss_f if loss_f < 0.1 else 0)
    lusd_reward = int(total_lusd_staked * (pf - sf))
    lusd_sp_loss = int(total_lusd_staked * (1 - sf))
    return (lusd_reward, lusd_sp_loss)