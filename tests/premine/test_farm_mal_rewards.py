from brownie._config import CONFIG
CONFIG.networks['mainnet-fork']['cmd_settings']['block_time'] = 10000
CONFIG.networks['mainnet-fork']['cmd_settings']['accounts'] = 100

import pytest
from decimal import Decimal

from scripts.common import estimate_rate_decay_params, calculate_rate_decay_reward, DAY_SECS, E18, E18d, UINT256_MAX
from scripts.simulation.gamma_farm import GammaFarmSimulator
from scripts.simulation.gamma_farm_py import GammaFarmPythonSimulator
from scripts.simulation.gamma_farm_naive import GammaFarmNaiveSimulator
from scripts.simulation.structs import Event, EventType, EpochData


def test_mal_rewards_decay(chain, history):
    num_epochs = 40
    eT = DAY_SECS       # epoch expected duration secs
    Q = 6000 * E18      # mal_to_distribute (6k MAL)
    T = num_epochs * eT # mal_distribution_period (40 days)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)  # mal_per_sec, mal_decay_factor
    py_sim = GammaFarmPythonSimulator(Q, T, R, F)
    # Deposit:
    py_sim.simulate_event(Event(0, EventType.DEPOSIT, 100*E18, user=0))
    # Run epochs:
    mal_rewards = [0, 0, 0, 0]
    expected_mal_rewards = [0, 0, 0, 0]
    ts = 0
    curR = R
    for i in range(4):
        for j in range(num_epochs // 4):
            ts += eT
            py_sim.simulate_event(Event(ts, EventType.NEW_EPOCH, data=EpochData(reward=0)))
            expected_mal_rewards[i] += eT * curR
            curR = curR * F // E18
        (_, _, mal_rewards[i], _, _) = py_sim.get_account_balances(0)
    py_sim.simulate_event(Event(ts, EventType.CLAIM, user=0))
    py_state = py_sim.gather_state()
    # Check balances:
    assert mal_rewards[0] / E18d == pytest.approx(Q//2 / E18d, rel=Decimal(1e-1))
    assert mal_rewards[3] / E18d == pytest.approx(Q / E18d, rel=Decimal(1e-9))
    for i in range(4):
        calculated_reward = calculate_rate_decay_reward(R, F, eT, (i + 1) * T // 4)
        assert mal_rewards[i] <= calculated_reward
        assert mal_rewards[i] / E18d == pytest.approx(calculated_reward / E18d, rel=Decimal(1e-9))
        epoch_mal_rewards = mal_rewards[i] - (mal_rewards[i - 1] if i > 0 else 0)
        assert expected_mal_rewards[i] / E18d == pytest.approx(epoch_mal_rewards / E18d, rel=Decimal(1e-9))
    user_mal_balance = py_state.userMalOut[0]
    farm_mal_balance = py_state.farmMalBalance
    assert farm_mal_balance == Q - user_mal_balance
    assert farm_mal_balance / E18d == pytest.approx(0, abs=Decimal(1e-9))
    assert user_mal_balance / E18d == pytest.approx(Q / E18d, abs=Decimal(1e-9))
    # Compare with exact:
    events = py_sim.get_events_history()
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, mal_abs=1e-14, user_mal_abs=1e-14)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F)
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_mal_rewards_decay_epochs_longer_than_expected(chain, history):
    num_epochs = 40
    eT = DAY_SECS       # epoch expected duration secs
    Q = 6000 * E18      # mal_to_distribute (6k MAL)
    T = num_epochs * eT # mal_distribution_period (40 days)
    (R, F) = estimate_rate_decay_params(Q, T, Q // 2, T // 4, eT)  # mal_per_sec, mal_decay_factor
    events = [] + \
        [Event(0, EventType.DEPOSIT, 100*E18, user=0)] + \
        [
            # Each epoch taking longer than expected duration:
            Event(2 * eT * (e + 1), EventType.NEW_EPOCH, data=EpochData(reward=10**14*int(e > 0))) \
                for e in range(0, num_epochs)
        ] + \
        [Event(2 * eT * num_epochs, EventType.CLAIM, user=0)]
    py_sim = GammaFarmPythonSimulator(Q, T, R, F)
    py_state = py_sim.simulate_events(events)
    # Check balances:
    user_mal_balance = py_state.userMalOut[0]
    farm_mal_balance = py_state.farmMalBalance
    assert farm_mal_balance == Q - user_mal_balance
    assert 0 < user_mal_balance <= Q
    # Compare with exact:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, user_mal_abs=1e-14, mal_abs=1e-14)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F)
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_mal_rewards_single_user(chain, history):
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 4320 * E18              # mal_to_distribute (4.32k MAL)
    T = 10 * DAY_SECS           # mal_distribution_period_secs (10 days)
    R = Q // T                  # mal_reward_per_second (0.005 MAL/sec)
    F = int(0.95 * E18)         # mal_decay_factor (0.95)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F)
    py_sim.simulate_event(Event(eT // 2, EventType.DEPOSIT, 100*E18, user=0))
    py_sim.simulate_event(Event(eT, EventType.NEW_EPOCH, data=EpochData(reward=0)))
    (_, _, mal_rewards1, _, _) = py_sim.get_account_balances(0)
    py_sim.simulate_event(Event(2*eT, EventType.NEW_EPOCH, data=EpochData(reward=10**14)))
    (_, _, mal_rewards2, _, _) = py_sim.get_account_balances(0)
    py_sim.simulate_event(Event(2*eT + 1, EventType.UNSTAKE, user=0))
    py_sim.simulate_event(Event(3*eT, EventType.NEW_EPOCH, data=EpochData(reward=10**14)))
    (_, _, mal_rewards3, _, _) = py_sim.get_account_balances(0)
    py_sim.simulate_event(Event(3*eT + eT // 4, EventType.WITHDRAW, user=0))
    py_state = py_sim.gather_state()
    # Check MAL balances:
    missed_reward = calculate_rate_decay_reward(R, F, eT, eT // 2)
    est_mal_rewards1 = calculate_rate_decay_reward(R, F, eT, eT) - missed_reward
    est_mal_rewards2 = calculate_rate_decay_reward(R, F, eT, 2 * eT) - missed_reward
    est_mal_rewards3 = calculate_rate_decay_reward(R, F, eT, 3 * eT) - missed_reward
    est_mal_rewards = calculate_rate_decay_reward(R, F, eT, 3 * eT + eT // 4) - missed_reward
    RELATIVE_PRECISION = 1e-5
    assert mal_rewards1 == pytest.approx(est_mal_rewards1, rel=RELATIVE_PRECISION)
    assert mal_rewards2 == pytest.approx(est_mal_rewards2, rel=RELATIVE_PRECISION)
    assert mal_rewards3 == pytest.approx(est_mal_rewards3, rel=RELATIVE_PRECISION)
    assert py_state.userMalOut[0] == pytest.approx(est_mal_rewards, rel=RELATIVE_PRECISION)
    # Compare with exact:
    events = py_sim.get_events_history()
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, mal_abs=1e-15, user_mal_abs=1e-15)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    events = py_sim.get_events_history()
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_mal_rewards_multiple_users(chain, history):
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 4320 * E18              # mal_to_distribute (4.32k MAL)
    T = 10 * DAY_SECS           # mal_distribution_period_secs (10 days)
    R = Q // T                  # mal_reward_per_second (0.005 MAL/sec)
    F = int(0.95 * E18)         # mal_decay_factor (0.95)
    events = [
        Event(10, EventType.DEPOSIT, 600*E18, user=0),
        Event(20, EventType.DEPOSIT, 200*E18, user=1),
        Event(30, EventType.DEPOSIT, 200*E18, user=2),
        Event(eT // 2, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(2 * eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(3 * eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(3 * eT + 10, EventType.UNSTAKE, user=0),
        Event(3 * eT + 20, EventType.UNSTAKE, user=1),
        Event(3 * eT + 30, EventType.UNSTAKE, user=2),
        Event(4 * eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(4 * eT + 10, EventType.WITHDRAW, user=0),
        Event(4 * eT + 20, EventType.WITHDRAW, user=1),
        Event(4 * eT + 30, EventType.WITHDRAW, user=2),
    ]
    curR = R
    # Calculate MAL rewards before staked:
    est_mal_rewards = [0] * 3
    est_mal_rewards[0] += (20 - 10) * curR
    est_mal_rewards[0] += (30 - 20) * curR * 3 // 4
    est_mal_rewards[0] += (eT // 2 - 30) * curR * 3 // 5
    est_mal_rewards[1] += (20 - 10) * curR // 4
    est_mal_rewards[1] += (eT // 2 - 30) * curR // 5
    est_mal_rewards[2] += (eT // 2 - 30) * curR // 5
    # Calculate MAL rewards during staking:
    epoch_mal_rewarded = (eT - eT // 2) * curR
    curR = curR * F // E18
    epoch_mal_rewarded += (2 * eT - eT) * curR
    curR = curR * F // E18
    epoch_mal_rewarded += (3 * eT - 2 * eT) * curR
    curR = curR * F // E18
    epoch_mal_rewarded += (4 * eT - 3 * eT) * curR
    est_mal_rewards[0] += epoch_mal_rewarded * 3 // 5
    est_mal_rewards[1] += epoch_mal_rewarded // 5
    est_mal_rewards[2] += epoch_mal_rewarded // 5
    # Calculate MAL rewards after unstaking:
    curR = curR * F // E18
    est_mal_rewards[0] += (4 * eT + 10 - (4 * eT)) * R * 3 // 5
    est_mal_rewards[1] += (4 * eT + 10 - (4 * eT)) * R // 5
    est_mal_rewards[1] += (4 * eT + 20 - (4 * eT + 10)) * R // 2
    est_mal_rewards[2] += (4 * eT + 10 - (4 * eT)) * R // 5
    est_mal_rewards[2] += (4 * eT + 20 - (4 * eT + 10)) * R // 2
    est_mal_rewards[2] += (4 * eT + 30 - (4 * eT + 20)) * R
    # Check final MAL balances:
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    for i in range(len(py_state.users)):
        assert py_state.userMalOut[i] == pytest.approx(est_mal_rewards[i], rel=1e-4)
    # Compare with exact:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, mal_abs=1e-15, user_mal_abs=1e-15)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_mal_rewards_both_available_and_staked(chain, history):
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 4320 * E18              # mal_to_distribute (4.32k MAL)
    T = 10 * DAY_SECS           # mal_distribution_period_secs (10 days)
    R = Q // T                  # mal_reward_per_second (0.005 MAL/sec)
    F = int(0.95 * E18)         # mal_decay_factor (0.95)
    events = [
        Event(10, EventType.DEPOSIT, 200*E18, user=0),
        Event(20, EventType.DEPOSIT, 200*E18, user=1),
        Event(eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(eT + eT // 2, EventType.DEPOSIT, 200*E18, user=1),
        Event(2 * eT, EventType.NEW_EPOCH, data=EpochData(reward=10**14)),
        Event(3 * eT - 20, EventType.UNSTAKE, user=0),
        Event(3 * eT - 10, EventType.UNSTAKE, user=1),
        Event(3 * eT, EventType.NEW_EPOCH, data=EpochData(reward=10**14)),
        Event(3 * eT + 10, EventType.WITHDRAW, user=0),
        Event(3 * eT + 20, EventType.WITHDRAW, user=1),
    ]
    # Calculate MAL rewards before staked:
    curR = R
    est_mal_rewards = [0] * 2
    est_mal_rewards[0] += (20 - 10) * curR
    est_mal_rewards[0] += (eT - 20) * curR // 2
    est_mal_rewards[1] += (eT - 20) * curR // 2
    # Calculate MAL rewards during staking:
    curR = curR * F // E18
    est_mal_rewards[0] += ((eT + eT // 2) - eT) * curR // 2
    est_mal_rewards[1] += ((eT + eT // 2) - eT) * curR // 2
    est_mal_rewards[0] += (2 * eT - (eT + eT // 2)) * curR // 3
    est_mal_rewards[1] += (2 * eT - (eT + eT // 2)) * curR * 2 // 3
    curR = curR * F // E18
    est_mal_rewards[0] += (3 * eT - 2 * eT) * curR // 3
    est_mal_rewards[1] += (3 * eT - 2 * eT) * curR * 2 // 3
    # Calculate MAL rewards after unstaking:
    curR = curR * F // E18
    est_mal_rewards[0] += (3 * eT + 10 - 3 * eT) * curR // 3
    est_mal_rewards[1] += (3 * eT + 10 - 3 * eT) * curR * 2 // 3
    est_mal_rewards[1] += (3 * eT + 20 - (3 * eT + 10)) * curR
    # Check final MAL balances:
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    for i in range(len(py_state.users)):
        assert py_state.userMalOut[i] == pytest.approx(est_mal_rewards[i], rel=1e-4)
    # Compare with exact:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, lusd_abs=1e-15, user_lusd_abs=1e-15, mal_abs=1e-15, user_mal_abs=1e-15)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)


def test_mal_rewards_distribution_ended(chain, history):
    eT = DAY_SECS               # estimated epoch duration secs
    Q = 4320 * E18              # mal_to_distribute (4.32k MAL)
    T = 10 * DAY_SECS           # mal_distribution_period_secs (10 days)
    R = Q // T                  # mal_reward_per_second (0.005 MAL/sec)
    F = E18                     # mal_decay_factor (1.0)
    events = [
        Event(eT // 4, EventType.DEPOSIT, 200*E18, user=0),
        Event(eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        # First epoch (after distribution is over first user requests unstake, second user deposits):
        Event(T + eT - 2, EventType.UNSTAKE, user=0),
        Event(T + eT - 1, EventType.DEPOSIT, 200*E18, user=1),
        Event(T + eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(T + 2 * eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(T + 2 * eT + 1, EventType.UNSTAKE, user=1),
        Event(T + 3 * eT, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(T + 3 * eT + 1, EventType.WITHDRAW, user=0),
        Event(T + 3 * eT + 2, EventType.WITHDRAW, user=1),
    ]
    # Check MAL balances:
    est_mal_rewards0 = R * (T - eT // 4)
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    assert py_state.userMalOut[0] == pytest.approx(est_mal_rewards0, rel=1e-4)
    assert py_state.userMalOut[1] == 0
    # Compare with exact:
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state)
    # Simulate:
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)
