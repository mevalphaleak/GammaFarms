from decimal import Decimal
import os

try:
    from scripts.common import DEBUG
    from scripts.simulation.structs import EventType, SimulationState
except:
    from structs import EventType, SimulationState
    from decimal import getcontext
    getcontext().prec = 77
    DEBUG = False


E18 = 10 ** 18
E18d = Decimal(10 ** 18)
UINT256_MAX = pow(2, 256) - 1


def dec_pow(a, n):
    def dec_mul(x, y):
        return (x * y + E18 // 2) // E18
    if n == 0:
        return E18
    y = E18
    x = a
    while n > 1:
        if n % 2 == 0:
            x = dec_mul(x, x)
            n = n // 2
        else:
            y = dec_mul(x, y)
            x = dec_mul(x, x)
            n = (n - 1) // 2
    return dec_mul(x, y)


def calculate_reward(R, F, eT, t):
    if F == E18:
        return R * t
    n = t // eT
    f_pow = dec_pow(F, n)
    (fa, fb) = (E18 - f_pow, E18 - F)
    cum_f = fa * E18 // fb
    return (R * cum_f * eT // E18) + (R * f_pow * (t - n * eT) // E18)


class GlobalState:
    def __init__(self):
        self.cumP = Decimal(1)
        self.cumS1 = Decimal(0)
        self.cumS2 = Decimal(0)


class UserState:
    def __init__(self, user):
        self.user = user
        self.lusdBalance = Decimal(0)
        self.lusdStaked = Decimal(0)
        self.malRewards = Decimal(0)
        self.lusdToStake = Decimal(0)
        self.lusdToUnstake = Decimal(0)
        self.lusdIn = Decimal(0)
        self.lusdOut = Decimal(0)
        self.malOut = Decimal(0)

    def __str__(self):
        v = [
            f"a={(self.lusdBalance-self.lusdStaked) / E18d:.18f}",
            f"s={self.lusdStaked / E18d:.18f}",
            f"m={self.malRewards / E18d:.18f}",
            f"s_in={self.lusdToStake / E18d:.18f}",
            f"s_out={self.lusdToUnstake / E18d:.18f}",
            f"LUSD_in={self.lusdIn / E18d:.18f}",
            f"LUSD_out={self.lusdOut / E18d:.18f}",
            f"MAL_out={self.malOut / E18d:.18f}",
        ]
        return f"{self.user}: {', '.join(v)}"


class GammaFarmNaiveSimulator:
    def __init__(self, Q, T, R, F, eT=86400, debug=False):
        self.Q = Decimal(Q)
        self.T = T
        self.R = Decimal(R)
        self.F = Decimal(F)
        self.eT = eT
        self.userState = {}  # user -> UserState (state at the beginning of ts)
        self.globalState = GlobalState()
        self.users = set()
        self.lastTs = 0
        self.epoch = 0
        self.isEmergency = False
        self.debug = debug or DEBUG
        self.totalLusdReward = Decimal(0)
        self.totalLusdSpLoss = Decimal(0)
        self.spCompoundedDeposit = Decimal(0)
        if self.debug:
            dir = f"{'/'.join(os.path.realpath(__file__).split('/')[0:-3])}/logs"
            os.makedirs(dir, exist_ok=True)
            self.fout = open(f"{dir}/log_naive.txt", "w")

    def simulate_events(self, events):
        for e in events:
            self.simulate_event(e)
        return self.gather_state()

    def simulate_event(self, e):
        if self.debug:
            self.fout.write(f"=========\n* {e}\n")
        (S, G) = (self.userState, self.globalState)
        if e.user is not None:
            self.users.add(e.user)
            if e.user not in S:
                S[e.user] = UserState(e.user)
        # MAL rewards:
        newTs = min(e.ts, self.T)
        totalLusd = sum([v.lusdBalance for v in S.values()])
        if self.lastTs < newTs <= self.T and totalLusd > 0:
            newMalReward = self._calculate_new_mal_reward(self.lastTs, newTs)
            for user in self.users:
                S[user].malRewards += newMalReward * S[user].lusdBalance / totalLusd
            G.cumS1 += newMalReward * G.cumP / totalLusd
            G.cumS2 += newMalReward / totalLusd
        self.lastTs = newTs
        # Process event:
        if e.type == EventType.DEPOSIT:
            amount = Decimal(e.amount)
            S[e.user].lusdBalance += amount
            S[e.user].lusdToStake += amount
            S[e.user].lusdIn += amount
        elif e.type == EventType.WITHDRAW:
            lusdWithdrawn = S[e.user].lusdBalance - S[e.user].lusdStaked
            if self.isEmergency:
                lusdWithdrawn += S[e.user].lusdStaked
                S[e.user].lusdStaked = 0
                S[e.user].lusdToUnstake = 0
            S[e.user].lusdToStake = 0
            S[e.user].lusdBalance -= lusdWithdrawn
            S[e.user].lusdOut += lusdWithdrawn
            S[e.user].malOut += S[e.user].malRewards
            S[e.user].malRewards = 0
        elif e.type == EventType.UNSTAKE:
            assert not self.isEmergency
            S[e.user].lusdToUnstake = S[e.user].lusdStaked
        elif e.type == EventType.UNSTAKE_AND_WITHDRAW:
            assert not self.isEmergency and S[e.user].lusdStaked > 0
            (lusdReward, totalStakedAfter) = e.data.get_epoch_results_decimal(self.spCompoundedDeposit)
            totalStakedBefore = sum([v.lusdStaked for v in S.values()])
            assert lusdReward == 0 and totalStakedBefore != 0 and totalStakedAfter != 0
            lusdStakedBefore = S[e.user].lusdStaked
            lusdStakedAfter = lusdStakedBefore * totalStakedAfter / totalStakedBefore
            lusdWithdrawn = lusdStakedAfter + (S[e.user].lusdBalance - lusdStakedBefore)
            assert lusdWithdrawn != 0
            S[e.user].lusdToStake = 0
            S[e.user].lusdStaked = 0
            S[e.user].lusdBalance = 0
            S[e.user].lusdToUnstake = 0
            S[e.user].lusdOut += lusdWithdrawn
            S[e.user].malOut += S[e.user].malRewards
            S[e.user].malRewards = 0
            self.totalLusdSpLoss += self.spCompoundedDeposit - totalStakedAfter
            self.spCompoundedDeposit = totalStakedAfter - lusdStakedAfter
        elif e.type == EventType.CLAIM:
            S[e.user].malOut += S[e.user].malRewards
            S[e.user].malRewards = 0
        elif e.type in [EventType.NEW_EPOCH, EventType.EMERGENCY_WITHDRAW, EventType.EMERGENCY_RECOVER]:
            # Update emergency state:
            if e.type in [EventType.NEW_EPOCH, EventType.EMERGENCY_WITHDRAW]:
                assert not self.isEmergency
                self.isEmergency = (e.type == EventType.EMERGENCY_WITHDRAW)
            elif e.type == EventType.EMERGENCY_RECOVER:
                assert self.isEmergency
                self.isEmergency = False
                self.spCompoundedDeposit = sum([v.lusdStaked for v in S.values()])
            # Account for reward and loss:
            if e.type in [EventType.NEW_EPOCH, EventType.EMERGENCY_WITHDRAW]:
                (lusdReward, totalStakedAfter) = e.data.get_epoch_results_decimal(self.spCompoundedDeposit)
                self.totalLusdReward += lusdReward
                self.totalLusdSpLoss += self.spCompoundedDeposit - totalStakedAfter
                self.spCompoundedDeposit = totalStakedAfter + lusdReward
                totalStakedBefore = sum([v.lusdStaked for v in S.values()])
                if totalStakedBefore > 0:
                    G.cumP *= (lusdReward + totalStakedAfter) / totalStakedBefore if totalStakedBefore > 0 else Decimal(1)
                    for user in self.users:
                        userLusdAvailable = (S[user].lusdBalance - S[user].lusdStaked)
                        userLusdReward = lusdReward * S[user].lusdStaked / totalStakedBefore
                        S[user].lusdStaked = S[user].lusdStaked * totalStakedAfter / totalStakedBefore + userLusdReward
                        S[user].lusdBalance = S[user].lusdStaked + userLusdAvailable
            # Stake/unstake before new epoch:
            if e.type in [EventType.NEW_EPOCH, EventType.EMERGENCY_WITHDRAW]:
                # Unstake:
                for user in self.users:
                    if S[user].lusdToUnstake > 0:
                        self.spCompoundedDeposit -= S[user].lusdStaked
                        S[user].lusdStaked = Decimal(0)
                        S[user].lusdToUnstake = Decimal(0)
                # Stake:
                for user in self.users:
                    if S[user].lusdToStake > 0:
                        self.spCompoundedDeposit += S[user].lusdToStake
                        S[user].lusdStaked += S[user].lusdToStake
                        S[user].lusdToStake = Decimal(0)
                # New epoch started:
                if e.type == EventType.EMERGENCY_WITHDRAW:
                    self.spCompoundedDeposit = 0
                self.epoch += 1
        if self.debug:
            self.print_state()


    def _calculate_new_mal_reward(self, t1, t2):
        assert t1 < t2
        m2 = calculate_reward(int(self.R), int(self.F), int(self.eT), t2)
        m1 = calculate_reward(int(self.R), int(self.F), int(self.eT), t1)
        return m2 - m1


    def print_state(self):
        (S, G) = (self.userState, self.globalState)
        v = [
            f"V={sum(S[u].lusdBalance for u in S) / E18d:.18f}",
            f"S={sum(S[u].lusdStaked for u in S) / E18d:.18f}",
            f"S_IN={sum(S[u].lusdToStake for u in S) / E18d:.18f}",
            f"S_OUT={sum(S[u].lusdToUnstake for u in S) / E18d:.18f}",
            f"P={G.cumP:.18f}",
            f"S1={G.cumS1:.18f}",
            f"S2={G.cumS2:.18f}",
        ]
        self.fout.write(f"  GLOBAL: {', '.join(v)}\n")
        for u in sorted(self.users):
            self.fout.write(f"  {S[u]}\n")

    def gather_state(self):
        s = SimulationState()
        (S, G) = (self.userState, self.globalState)
        s.users = self.users
        for user in self.users:
            s.userLusdIn[user] = S[user].lusdIn
            s.userLusdOut[user] = S[user].lusdOut
            s.userMalOut[user] = S[user].malOut
            (s.lusdAvailable[user], s.lusdStaked[user], s.malRewards[user], _, _) = self.get_account_balances(user)
        (s.totalLusd, s.totalLusdStaked) = self.get_total_balances()
        s.P = G.cumP * E18d
        s.S1 = G.cumS1 * E18d
        s.S2 = G.cumS2 * E18d
        s.epoch = self.epoch
        s.totalUserLusdIn = sum(s.userLusdIn.values())
        s.totalUserLusdOut = sum(s.userLusdOut.values())
        s.totalMalOut = sum(s.userMalOut.values())
        s.totalMalSupply = self.Q
        s.totalLusdReward = self.totalLusdReward
        s.totalLusdSpLoss = self.totalLusdSpLoss
        s.spCompoundedDeposit = self.spCompoundedDeposit
        s.farmLusdBalance = s.totalUserLusdIn + self.totalLusdReward - self.totalLusdSpLoss - s.totalUserLusdOut - s.spCompoundedDeposit
        s.farmMalBalance = self.Q - s.totalMalOut
        assert int(s.farmLusdBalance) >= 0
        assert sum(int(v) for v in s.malRewards.values()) + sum(int(v) for v in s.userMalOut.values()) <= s.totalMalSupply
        return s

    def get_total_balances(self):
        total_lusd = sum(self.userState[u].lusdBalance for u in self.userState)
        total_lusd_staked = 0 if self.isEmergency else sum(self.userState[u].lusdStaked for u in self.userState)
        return (total_lusd, total_lusd_staked)

    def get_account_balances(self, user):
        lusd_available = self.userState[user].lusdBalance - self.userState[user].lusdStaked
        lusd_staked = self.userState[user].lusdStaked
        lusd_to_stake = self.userState[user].lusdToStake
        should_unstake = self.userState[user].lusdToUnstake > 0
        if self.isEmergency:
            lusd_available = self.userState[user].lusdBalance
            lusd_staked = 0
            lusd_to_stake += (0 if should_unstake else self.userState[user].lusdStaked)
            should_unstake = False
        return (lusd_available, lusd_staked, self.userState[user].malRewards, lusd_to_stake, should_unstake)
