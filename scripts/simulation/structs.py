from collections import defaultdict
from decimal import Decimal
from enum import Enum
import pytest


class EventType(Enum):
    DEPOSIT = "deposit"
    UNSTAKE = "unstake"
    WITHDRAW = "withdraw"
    UNSTAKE_AND_WITHDRAW = "unstakeAndWithdraw"
    CLAIM = "claim"
    NEW_EPOCH = "startNewEpoch"
    EMERGENCY_WITHDRAW = "emergencyWithdraw"
    EMERGENCY_RECOVER = "emergencyRecover"


class Event:
    def __init__(self, ts, ev_type, amount=None, user=None, data=None):
        assert (
            (ev_type in [EventType.DEPOSIT] and user is not None and amount is not None) or
            (ev_type in [EventType.UNSTAKE, EventType.WITHDRAW, EventType.CLAIM] and user is not None) or
            (ev_type in [EventType.UNSTAKE_AND_WITHDRAW] and user is not None and data is not None) or
            (ev_type in [EventType.NEW_EPOCH, EventType.EMERGENCY_WITHDRAW] and data is not None) or
            (ev_type == EventType.EMERGENCY_RECOVER)
        )
        self.ts = ts
        self.type = ev_type
        self.amount = amount
        self.user = user
        self.data = data
    def __str__(self):
        ts_str = f"ts={self.ts}"
        user_str = f"user={self.user}" if self.user is not None else None
        amount_str = f"amount={'UINT256_MAX' if self.amount == pow(2, 256) - 1 else self.amount}" if self.amount is not None else None
        data_str = str(self.data) if self.data else None
        args_str = ", ".join(list(filter(lambda x: x, [ts_str, user_str, amount_str, data_str])))
        return f"{self.type.value}({args_str})"


class EpochData:
    # EpochData(reward=10e18) - reward of 10 LUSD, no Stability Pool loss
    # EpochData(reward=10e18, loss=1e18) - reward of 10 LUSD and SP loss of 1 LUSD
    def __init__(self, reward=None, loss=None, pf=None, sf=None):
        assert (reward is not None) or (pf is not None and sf is not None and pf >= sf)
        self.reward = reward
        self.loss = loss
        self.pf = pf
        self.sf = sf
    def __str__(self):
        reward_str = f"reward={self.reward}" if self.reward is not None else None
        loss_str = f"loss={self.loss}" if self.loss is not None else None
        pf_str = f"pf={self.pf}" if self.pf is not None else None
        sf_str = f"sf={self.sf}" if self.sf is not None else None
        return ", ".join(list(filter(lambda x: x, [reward_str, loss_str, pf_str, sf_str])))

    # Returns (lusd_reward, new_lusd_sp_staked)
    def get_epoch_results(self, total_lusd_staked):
        (lusd_reward, new_lusd_sp_staked) = (0, total_lusd_staked)
        # Calculate SP loss and new staked value:
        if self.loss is not None:
            new_lusd_sp_staked = total_lusd_staked - self.loss
        elif self.sf is not None:
            new_lusd_sp_staked = self.sf * total_lusd_staked
        # Calculate SP reward:
        if self.reward is not None:
            lusd_reward = self.reward
        elif self.pf is not None:
            lusd_reward = self.pf * total_lusd_staked - new_lusd_sp_staked
        # Checks:
        return (lusd_reward, new_lusd_sp_staked)

    def get_epoch_results_decimal(self, total_lusd_staked):
        (lusd_reward, new_lusd_sp_staked) = self.get_epoch_results(total_lusd_staked)
        return (Decimal(lusd_reward), Decimal(new_lusd_sp_staked))


class PrecisionCompareResult:
    def __init__(self):
        self.user_mal_abs_err = (0, "")
        self.user_mal_rel_err = (0, "")
        self.user_lusd_abs_err = (0, "")
        self.user_lusd_rel_err = (0, "")
        self.mal_out_abs_err = (0, "")
        self.mal_out_rel_err = (0, "")
        self.lusd_out_abs_err = (0, "")
        self.lusd_out_rel_err = (0, "")
        self.total_lusd_abs_err = (0, "")
    def __str__(self):
        def to_str(name, v):
            return f"  {name}: {v[0]:.2e} ({v[1]})" if v[0] > 1e-18 else None
        strs = [
            to_str("user_mal_abs_err", self.user_mal_abs_err),
            to_str("user_mal_rel_err", self.user_mal_rel_err),
            to_str("user_lusd_abs_err", self.user_lusd_abs_err),
            to_str("user_lusd_rel_err", self.user_lusd_rel_err),
            to_str("mal_out_abs_err", self.mal_out_abs_err),
            to_str("mal_out_rel_err", self.mal_out_rel_err),
            to_str("lusd_out_abs_err", self.lusd_out_abs_err),
            to_str("lusd_out_rel_err", self.lusd_out_rel_err),
            to_str("total_lusd_abs_err", self.total_lusd_abs_err),
        ]
        return "\n".join(s for s in strs if s is not None)


class SimulationState:
    SKIP_COMPARISON = -1

    def __init__(self):
        self.users = set()
        self.epoch = 0
        self.totalLusd = 0
        self.totalLusdStaked = 0
        self.lusdAvailable = defaultdict(lambda: 0)
        self.lusdStaked = defaultdict(lambda: 0)
        self.malRewards = defaultdict(lambda: 0)
        self.P = 0
        self.S1 = 0
        self.S2 = 0
        self.farmLusdBalance = 0
        self.farmMalBalance = 0
        self.userLusdIn = defaultdict(lambda: 0)
        self.userLusdOut = defaultdict(lambda: 0)
        self.userMalOut = defaultdict(lambda: 0)
        self.totalUserLusdIn = 0
        self.totalUserLusdOut = 0
        self.totalMalSupply = 0
        self.totalMalOut = 0
        self.totalLusdReward = 0
        self.totalLusdSpLoss = 0
        self.spCompoundedDeposit = 0

    def equals(self, s, lusd_abs=0, mal_abs=0, user_mal_abs=0, user_lusd_abs=0, snap_lusd_abs=None, snap_mal_abs=None, debug=False):
        return self._equals(s, lusd_abs, mal_abs, user_mal_abs, user_lusd_abs, snap_lusd_abs, snap_mal_abs, debug)

    def compare(self, s):
        result = PrecisionCompareResult()
        self._equals(s, result)
        return result

    def _equals(self, s, lusd_abs=0, mal_abs=0, user_mal_abs=0, user_lusd_abs=0, snap_lusd_abs=None, snap_mal_abs=None, debug=False, result=None):
        if debug and result is None:
            result = PrecisionCompareResult()
        eq = True
        eq &= self.equals_sets('users', self.users, s.users, debug=debug)
        eq &= self.equals_ints('epoch', self.epoch, s.epoch, decimals=0, debug=debug)
        eq &= self.equals_ints('totalUserLusdIn', self.totalUserLusdIn, s.totalUserLusdIn, abs_thresh=0, debug=debug)
        eq &= self.equals_ints('totalMalSupply', self.totalMalSupply, s.totalMalSupply, abs_thresh=0, debug=debug)
        # Total LUSD and Total LUSD Staked:
        eq &= self.equals_ints('totalLusd', self.totalLusd, s.totalLusd, abs_thresh=lusd_abs, debug=debug, result=result)
        eq &= self.equals_ints('totalLusdStaked', self.totalLusdStaked, s.totalLusdStaked, abs_thresh=lusd_abs, debug=debug, result=result)
        # Total outs:
        eq &= self.equals_ints('totalUserLusdOut', self.totalUserLusdOut, s.totalUserLusdOut, abs_thresh=lusd_abs, debug=debug, result=result)
        eq &= self.equals_ints('totalMalOut', self.totalMalOut, s.totalMalOut, abs_thresh=mal_abs, debug=debug, result=result)
        eq &= self.equals_ints('totalMalRewards', sum(self.malRewards.values()), sum(s.malRewards.values()), abs_thresh=mal_abs, debug=debug, result=result)
        # Mixed balances:
        eq &= self.equals_ints('totalLusdReward', self.totalLusdReward, s.totalLusdReward, abs_thresh=lusd_abs, debug=debug)
        eq &= self.equals_ints('totalLusdSpLoss', self.totalLusdSpLoss, s.totalLusdSpLoss, abs_thresh=lusd_abs, debug=debug)
        eq &= self.equals_ints('spCompoundedDeposit', self.spCompoundedDeposit, s.spCompoundedDeposit, abs_thresh=lusd_abs, debug=debug)
        eq &= self.equals_ints('farmLusdBalance', self.farmLusdBalance, s.farmLusdBalance, abs_thresh=lusd_abs, debug=debug)
        eq &= self.equals_ints('farmMalBalance', self.farmMalBalance, s.farmMalBalance, abs_thresh=mal_abs, debug=debug)
        # Snapshot:
        if snap_lusd_abs != SimulationState.SKIP_COMPARISON:
            snap_lusd_abs = lusd_abs if snap_lusd_abs is None else snap_lusd_abs
            eq &= self.equals_ints('P', self.P, s.P, abs_thresh=snap_lusd_abs, debug=debug)
        elif debug:
            self._warn_skipped_comparison('P', self.P, s.P)
        if snap_mal_abs != SimulationState.SKIP_COMPARISON:
            snap_mal_abs = mal_abs if snap_mal_abs is None else snap_mal_abs
            eq &= self.equals_ints('S1', self.S1, s.S1, abs_thresh=snap_mal_abs, debug=debug)
            eq &= self.equals_ints('S2', self.S2, s.S2, abs_thresh=snap_mal_abs, debug=debug)
        elif debug:
            self._warn_skipped_comparison('S1', self.S1, s.S1)
            self._warn_skipped_comparison('S2', self.S2, s.S2)
        # User balances:
        for user in sorted(self.users):
            eq &= self.equals_ints(f"user={user}: lusdAvailable", self.lusdAvailable[user], s.lusdAvailable[user], abs_thresh=user_lusd_abs, debug=debug, result=result)
            eq &= self.equals_ints(f"user={user}: lusdStaked", self.lusdStaked[user], s.lusdStaked[user], abs_thresh=user_lusd_abs, debug=debug, result=result)
            eq &= self.equals_ints(f"user={user}: malRewards", self.malRewards[user], s.malRewards[user], abs_thresh=user_mal_abs, debug=debug, result=result)
            eq &= self.equals_ints(f"user={user}: userLusdIn", self.userLusdIn[user], s.userLusdIn[user], abs_thresh=0, debug=debug, result=result)
            eq &= self.equals_ints(f"user={user}: userLusdOut", self.userLusdOut[user], s.userLusdOut[user], abs_thresh=user_lusd_abs, debug=debug, result=result)
            eq &= self.equals_ints(f"user={user}: userMalOut", self.userMalOut[user], s.userMalOut[user], abs_thresh=user_mal_abs, debug=debug, result=result)
        if debug:
            print(f"States are {'equal' if eq else 'different'}")
            print(str(result))
        return eq

    def equals_ints(self, name, v1, v2, abs_thresh=0, decimals=18, debug=False, result=None):
        (d1, d2) = (int(v1) / Decimal(10**decimals), int(v2) / Decimal(10**decimals))
        (abs_err, rel_err) = self._compare(d1, d2)
        if result is not None:
            self._update_result(result, name, d1, d2, abs_err, rel_err)
        if abs_err <= Decimal(abs_thresh):
            return True
        if debug:
            print(self._debug_str(name, d1, d2, abs_err, rel_err))
        return False

    def equals_sets(self, name, s1, s2, debug=False):
        if set(s1) == set(s2):
            return True
        if debug:
            print(f"{name}: {set(s1)} vs {set(s2)}")
        return False

    def _warn_skipped_comparison(self, name, v1, v2, decimals=18):
        (d1, d2) = (int(v1) / Decimal(10**decimals), int(v2) / Decimal(10**decimals))
        (abs_err, rel_err) = self._compare(d1, d2)
        print(f"(hint) Skipped comparing {self._debug_str(name, d1, d2, abs_err, rel_err)}")

    def _compare(self, d1, d2):
        rel_err = Decimal(0) if (d1, d2) == (0, 0) else (
            Decimal("inf") if d1 == 0 or d2 == 0 else abs(d1 / d2 - Decimal(1))
        )
        return abs(d1 - d2), rel_err

    def _debug_str(self, name, d1, d2, abs_err, rel_err):
        return f"{name}: {d1:.18f} vs {d2:.18f} (abs={abs_err:.2e}, rel={rel_err:.2e})"

    def _update_result(self, result, name, d1, d2, abs_err, rel_err):
        def debug_str():
            return self._debug_str(name, d1, d2, abs_err, rel_err)
        if name.startswith('user') and 'mal' in name.lower():
            if abs_err > result.user_mal_abs_err[0]:
                result.user_mal_abs_err = (abs_err, debug_str())
            if rel_err > result.user_mal_rel_err[0]:
                result.user_mal_rel_err = (rel_err, debug_str())
            return
        if name.startswith('user') and 'lusd' in name.lower():
            if abs_err > result.user_lusd_abs_err[0]:
                result.user_lusd_abs_err = (abs_err, debug_str())
            if rel_err > result.user_lusd_rel_err[0]:
                result.user_lusd_rel_err = (rel_err, debug_str())
            return
        if name == 'totalMalOut' or name == 'totalMalRewards':
            if abs_err > result.mal_out_abs_err[0]:
                result.mal_out_abs_err = (abs_err, debug_str())
            if rel_err > result.mal_out_rel_err[0]:
                result.mal_out_rel_err = (rel_err, debug_str())
            return
        if name == 'totalUserLusdOut':
            if abs_err > result.lusd_out_abs_err[0]:
                result.lusd_out_abs_err = (abs_err, debug_str())
            if rel_err > result.lusd_out_rel_err[0]:
                result.lusd_out_rel_err = (rel_err, debug_str())
            return
        if name == 'totalLusd' or name == 'totalLusdStaked':
            if abs_err > result.total_lusd_abs_err[0]:
                result.total_lusd_abs_err = (abs_err, debug_str())
            return