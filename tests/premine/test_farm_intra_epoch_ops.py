from brownie._config import CONFIG
CONFIG.networks['mainnet-fork']['cmd_settings']['block_time'] = 10000
CONFIG.networks['mainnet-fork']['cmd_settings']['accounts'] = 100

from scripts.common import E18, E18d, UINT256_MAX
from scripts.simulation.gamma_farm import GammaFarmSimulator
from scripts.simulation.gamma_farm_py import GammaFarmPythonSimulator
from scripts.simulation.gamma_farm_naive import GammaFarmNaiveSimulator
from scripts.simulation.structs import Event, EventType, EpochData

import pytest


def test_intra_emergency_epoch_operations(chain, history):
    # user: init_deposit, [ action before emergency withdraw | action before emergency recover ]
    # user0: 200, [ ------------ | ------------ ]
    # user1: 200, [ unstake      | ------------ ]
    # user2: 200, [ deposit(200) | ------------ ]
    # user3:   0, [ deposit(200) | ------------ ]
    # user4: 200, [ deposit(200) | withdraw(all)]
    # user5: 200, [ ------------ | withdraw(all)]
    # user6: 200, [ ------------ | deposit(200) ]
    # user7:   0, [ ------------ | deposit(200) ]
    Q = 6000*E18    # mal_to_distribute (6k MAL)
    T = 5*60        # mal_distribution_period_secs (5 mins)
    R = Q // T      # mal_reward_per_sec
    F = E18         # mal_decay_factor (1.0)
    eT = T
    events = [
        Event(0, EventType.DEPOSIT, 200*E18, user=0),
        Event(0, EventType.DEPOSIT, 200*E18, user=1),
        Event(0, EventType.DEPOSIT, 200*E18, user=2),
        Event(0, EventType.DEPOSIT, 200*E18, user=4),
        Event(0, EventType.DEPOSIT, 200*E18, user=5),
        Event(0, EventType.DEPOSIT, 200*E18, user=6),
        Event(60, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(75, EventType.UNSTAKE, user=1),
        Event(75, EventType.DEPOSIT, 200*E18, user=2),
        Event(75, EventType.DEPOSIT, 200*E18, user=3),
        Event(75, EventType.DEPOSIT, 200*E18, user=4),
        Event(90, EventType.EMERGENCY_WITHDRAW, data=EpochData(reward=160*E18)),
        Event(105, EventType.WITHDRAW, user=4),
        Event(105, EventType.WITHDRAW, user=5),
        Event(105, EventType.DEPOSIT, 200*E18, user=6),
        Event(105, EventType.DEPOSIT, 200*E18, user=7),
        Event(120, EventType.EMERGENCY_RECOVER),
    ]
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, lusd_abs=1e-15, mal_abs=1e-14, user_lusd_abs=1e-15, user_mal_abs=1e-14)
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)



def test_mixed_intra_epoch_operations(chain, history):
    # user0: deposit, unstake, withdraw (3 full epochs) {1, 16, 21}
    # user1: deposit x3, unstake, withdraw {2, 2, 6, 14, 16} (subsequent deposits)
    # user2: deposit/unstake on before/after epoch ts {5, 5, 10, 10}, withdraw {11, 16} (epoch same-ts events)
    # user2: deposit again, unstake, withdraw {26, 36, 40} (returning user)
    # user3: deposit/withdraw {12, 13} (intra-epoch actions)
    # user4: deposit/withdraw {14, 14} (same-ts deposit/withdraw)
    # epochs: [0, 5), [5, 10), [10, 15), [15, 20), [20, 25), [25, 30), [30, 35), [35, 40)
    Q = 6000*E18        # mal_to_distribute (6k MAL)
    T = 30              # mal_distribution_period_secs (30 secs)
    R = Q // T          # mal_reward_per_sec
    F = int(0.99*E18)   # mal_decay_factor
    eT = 1
    events = [
        # epoch0:
        Event(1, EventType.DEPOSIT, 100*E18, user=0),
        Event(2, EventType.DEPOSIT, 200*E18, user=1),
        Event(2, EventType.DEPOSIT, 100*E18, user=1),
        Event(5, EventType.DEPOSIT, 100*E18, user=2),
        # epoch1:
        Event(5, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(5, EventType.UNSTAKE, user=2),
        Event(6, EventType.DEPOSIT, 100*E18, user=1),
        Event(10, EventType.DEPOSIT, 100*E18, user=2),
        # epoch2:
        Event(10, EventType.NEW_EPOCH, data=EpochData(reward=600*E18, loss=100*E18)),
        Event(10, EventType.UNSTAKE, user=2),
        Event(11, EventType.WITHDRAW, user=2),
        Event(12, EventType.DEPOSIT, 10000*E18, user=3),
        Event(13, EventType.WITHDRAW, user=3),
        Event(14, EventType.DEPOSIT, 100*E18, user=4),
        Event(14, EventType.WITHDRAW, user=4),
        Event(14, EventType.UNSTAKE, user=1),
        # epoch3:
        Event(15, EventType.NEW_EPOCH, data=EpochData(reward=100*E18, loss=600*E18)),
        Event(16, EventType.UNSTAKE, user=0),
        Event(16, EventType.WITHDRAW, user=1),
        Event(16, EventType.WITHDRAW, user=2),
        # epoch4:
        Event(20, EventType.NEW_EPOCH, data=EpochData(reward=100*E18)),
        Event(21, EventType.WITHDRAW, user=0),
        # epoch5 (empty at start):
        Event(25, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        Event(26, EventType.DEPOSIT, 100*E18, user=2),
        # epoch6:
        Event(30, EventType.NEW_EPOCH, data=EpochData(reward=0)),
        # epoch7:
        Event(35, EventType.NEW_EPOCH, data=EpochData(reward=10*E18, loss=9*E18)),
        Event(36, EventType.UNSTAKE, user=2),
        # epoch8:
        Event(40, EventType.NEW_EPOCH, data=EpochData(reward=10*E18, loss=10*E18)),
        Event(40, EventType.WITHDRAW, user=2),
    ]
    py_sim = GammaFarmPythonSimulator(Q, T, R, F, eT)
    py_state = py_sim.simulate_events(events)
    exact_sim = GammaFarmNaiveSimulator(Q, T, R, F, eT)
    exact_state = exact_sim.simulate_events(events)
    assert py_state.equals(exact_state, mal_abs=1e-13, user_mal_abs=1e-13)
    sim = GammaFarmSimulator(chain, history, Q, T, R, F, eT)
    state = sim.simulate_events(events)
    assert state.equals(py_state)
