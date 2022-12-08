from collections import defaultdict
from decimal import Decimal
import os

try:
    from scripts.common import DEBUG
    from scripts.simulation.structs import EventType, SimulationState
except:
    from structs import EventType, SimulationState
    DEBUG = False


E18 = 10 ** 18
E18d = Decimal(E18)
UINT256_MAX = pow(2, 256) - 1


class GammaMath:
    @staticmethod
    def decPow(a, n):
        def decMul(x, y):
            return (x * y + E18 // 2) // E18
        if n == 0:
            return E18
        y = E18
        x = a
        while n > 1:
            if n % 2 == 0:
                x = decMul(x, x)
                n = n // 2
            else:
                y = decMul(x, y)
                x = decMul(x, x)
                n = (n - 1) // 2
        return decMul(x, y)


class TestStabilityPool:
    def __init__(self):
        self.totalLUSDDeposits = 0
    def provideToSP(self, amount):
        self.totalLUSDDeposits += amount
    def withdrawFromSP(self, amount):
        amount = min(amount, self.totalLUSDDeposits)
        self.totalLUSDDeposits -= amount
    def getCompoundedLUSDDeposit(self):
        return self.totalLUSDDeposits
    def setCompoundedLUSDDeposit(self, totalLUSDDeposits):
        assert totalLUSDDeposits <= self.totalLUSDDeposits
        self.totalLUSDDeposits = totalLUSDDeposits


def _packAccountStakeData(_lusdToStake, _lusdStaked, _epoch, _shouldUnstake):
    assert 0 <= _lusdToStake < (1 << 112)
    assert 0 <= _lusdStaked < (1 << 112)
    return (_lusdToStake << 144) | (_lusdStaked << 32) | (_epoch << 1) | (1 if _shouldUnstake else 0)


def _unpackAccountStakeData(stakeData):
    _lusdToStake = (stakeData >> 144)
    _lusdStaked = (stakeData >> 32) & ((1 << 112) - 1)
    _epoch = (stakeData >> 1) & ((1 << 31) - 1)
    _shouldUnstake = (stakeData & 1) == 1
    return (_lusdToStake, _lusdStaked, _epoch, _shouldUnstake)


class Snapshot:
    def __init__(self, P=0, S1=0, S2=0):
        self.lusdProfitFactorCumP = P
        self.malRewardPerStakedCumS = S1
        self.malRewardPerAvailableCumS = S2
    def __str__(self):
        return f"(P={self.lusdProfitFactorCumP}, S1={self.malRewardPerStakedCumS}, S2={self.malRewardPerAvailableCumS})"


class AccountBalances:
    def __init__(self, lusdStakeData=0, malRewards=0, malRewardPerAvailableCumS=0, lusdUnstaked=0):
        self.lusdStakeData = lusdStakeData
        self.malRewards = malRewards
        self.malRewardPerAvailableCumS = malRewardPerAvailableCumS
        self.lusdUnstaked = lusdUnstaked
    def __str__(self):
        (lusdToStake, lusdStaked, _, shouldUnstake) = _unpackAccountStakeData(self.lusdStakeData)
        lusdAvailable = lusdToStake + self.lusdUnstaked
        return f"(a={lusdAvailable}, s={lusdStaked}, m={self.malRewards}, S2={self.malRewardPerAvailableCumS}, s_in={lusdToStake}, s_out={shouldUnstake})"


class GammaFarmPythonSimulator:
    DECIMAL_PRECISION = E18

    def __init__(self, malToDistribute, malDistributionPeriodSeconds, malRewardPerSecond, malDecayFactor, malDecayPeriodSeconds=86400, debug=False):
        self.lusdStabilityPool = TestStabilityPool()
        self.blockTimestamp = 0
        # --- Global MAL parameters ---
        self.deploymentTime = 0
        self.malDistributionEndTime = malDistributionPeriodSeconds
        self.malDecayPeriodSeconds = malDecayPeriodSeconds
        self.malDecayFactor = malDecayFactor
        self.malToDistribute = malToDistribute
        self.malRewardPerSecond = malRewardPerSecond
        # --- Total balances and state variables ---
        self.totalLusd = 0
        self.totalLusdStaked = 0
        self.totalLusdToStake = 0
        self.totalLusdToUnstake = 0
        self.lastTotalMalRewards = 0
        self.lastMalRewardPerAvailableCumS = 0
        # --- Per account variables ---
        self.accountBalances = defaultdict(lambda: AccountBalances(0, 0, 0, 0))
        # --- Epoch variables ---
        self.epochSnapshots = defaultdict(lambda: Snapshot(0, 0, 0))
        self.previousResetEpoch = defaultdict(lambda: 0)
        self.epochSnapshots[0].lusdProfitFactorCumP = self.DECIMAL_PRECISION
        self.epochStartTime = 0
        self.epoch = 0
        self.lastResetEpoch = 0
        # --- Emergency variables ---
        self.isEmergencyState = False
        # --- Debug ---
        self.events_history = []
        self.users = set()
        self.userLusdIn = defaultdict(lambda: 0)  # debug
        self.userLusdOut = defaultdict(lambda: 0)  # debug
        self.userMalOut = defaultdict(lambda: 0)  # debug
        self.totalLusdReward = 0  # debug
        self.totalLusdSpLoss = 0  # debug
        self.debug = debug or DEBUG  # debug
        if self.debug:
            dir = f"{'/'.join(os.path.realpath(__file__).split('/')[0:-3])}/logs"
            os.makedirs(dir, exist_ok=True)
            self.fout = open(f"{dir}/log_py.txt", "w")


    # --- Account methods ---

    def deposit(self, e):
        (self.blockTimestamp, msgSender, _lusdAmount) = (e.ts, e.user, e.amount)
        assert _lusdAmount >= E18
        newLastMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        oldBalances = self.accountBalances[msgSender]
        newBalances = self._calculateAccountBalances(oldBalances, newLastMalRewardPerAvailableCumS)
        # Transfer LUSD:
        self.userLusdIn[msgSender] += _lusdAmount
        # Update total balances:
        self.totalLusd += _lusdAmount
        self.totalLusdToStake += _lusdAmount
        # Update account balances:
        (lusdToStake, lusdStaked, accountEpoch, shouldUnstake) = _unpackAccountStakeData(newBalances.lusdStakeData)
        newBalances.lusdStakeData = _packAccountStakeData(lusdToStake + _lusdAmount, lusdStaked, accountEpoch, shouldUnstake)
        self._updateAccountBalances(msgSender, oldBalances, newBalances)

    def unstake(self, e):
        (self.blockTimestamp, msgSender) = (e.ts, e.user)
        assert not self.isEmergencyState
        newLastMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        oldBalances = self.accountBalances[msgSender]
        newBalances = self._calculateAccountBalances(oldBalances, newLastMalRewardPerAvailableCumS)
        (lusdToStake, lusdStaked, accountEpoch, shouldUnstake) = _unpackAccountStakeData(newBalances.lusdStakeData)
        assert lusdStaked != 0
        # Update total balances:
        if not shouldUnstake:
            self.totalLusdToUnstake += lusdStaked
        # Update account balances:
        newBalances.lusdStakeData = _packAccountStakeData(lusdToStake, lusdStaked, accountEpoch, True)
        self._updateAccountBalances(msgSender, oldBalances, newBalances)

    def withdraw(self, e):
        (self.blockTimestamp, msgSender) = (e.ts, e.user)
        newLastMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        oldBalances = self.accountBalances[msgSender]
        newBalances = self._calculateAccountBalances(oldBalances, newLastMalRewardPerAvailableCumS)
        (lusdToStake, lusdStaked, accountEpoch, shouldUnstake) = _unpackAccountStakeData(newBalances.lusdStakeData)
        isEmergencyState_ = self.isEmergencyState
        # Allow withdrawing "staked" balance during emergency:
        _lusdAmountWithdrawn = lusdToStake + newBalances.lusdUnstaked + (lusdStaked if isEmergencyState_ else 0)
        assert _lusdAmountWithdrawn != 0
        # Transfer LUSD:
        self.userLusdOut[msgSender] += _lusdAmountWithdrawn
        # Transfer MAL:
        if (newBalances.malRewards != 0):
            self.userMalOut[msgSender] += newBalances.malRewards
            newBalances.malRewards = 0
        # Update total balances:
        self.totalLusd -= _lusdAmountWithdrawn
        if (lusdToStake != 0):
            self.totalLusdToStake -= lusdToStake
            lusdToStake = 0
        if (isEmergencyState_ and lusdStaked != 0):
            self.totalLusdStaked -= lusdStaked
            lusdStaked = 0
        # Update account balances:
        newBalances.lusdStakeData = _packAccountStakeData(lusdToStake, lusdStaked, accountEpoch, shouldUnstake)
        newBalances.lusdUnstaked = 0
        self._updateAccountBalances(msgSender, oldBalances, newBalances)
        return _lusdAmountWithdrawn

    def unstakeAndWithdraw(self, e):
        (self.blockTimestamp, msgSender) = (e.ts, e.user)
        (lusdReward, totalLusdStakedAfter) = self._mock_epoch_reward_and_loss(e)
        assert not self.isEmergencyState and lusdReward == 0
        newLastMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        oldBalances = self.accountBalances[msgSender]
        newBalances = self._calculateAccountBalances(oldBalances, newLastMalRewardPerAvailableCumS)
        (lusdToStake, lusdStaked, _, shouldUnstake) = _unpackAccountStakeData(newBalances.lusdStakeData)
        assert lusdStaked != 0
        # Get staked LUSD amount at epoch start and after loss:
        totalLusdStakedBefore = self.totalLusdStaked
        assert totalLusdStakedBefore != 0 and totalLusdStakedAfter != 0
        # Calculate account new staked amount:
        lusdWithdrawnFromSP = lusdStaked * totalLusdStakedAfter // totalLusdStakedBefore
        assert lusdWithdrawnFromSP != 0
        # Withdraw from stability pool:
        self.lusdStabilityPool.withdrawFromSP(lusdWithdrawnFromSP)
        _lusdAmountWithdrawn = lusdWithdrawnFromSP
        # Withdraw from available balance:
        _lusdAmountWithdrawn += lusdToStake + newBalances.lusdUnstaked
        # Transfer LUSD:
        self.userLusdOut[msgSender] += _lusdAmountWithdrawn
        # Transfer MAL:
        if (newBalances.malRewards != 0):
            self.userMalOut[msgSender] += newBalances.malRewards
        # Update total balances:
        self.totalLusd -= lusdStaked + lusdToStake + newBalances.lusdUnstaked
        self.totalLusdStaked = totalLusdStakedBefore - lusdStaked
        if (lusdToStake != 0):
            self.totalLusdToStake -= lusdToStake
        if (shouldUnstake):
            self.totalLusdToUnstake -= lusdStaked
        # Update account balances:
        self.accountBalances[msgSender] = AccountBalances()

    def claim(self, e):
        (self.blockTimestamp, msgSender) = (e.ts, e.user)
        newLastMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        oldBalances = self.accountBalances[msgSender]
        newBalances = self._calculateAccountBalances(oldBalances, newLastMalRewardPerAvailableCumS)
        assert newBalances.malRewards != 0
        # Transfer MAL:
        if newBalances.malRewards != 0:
            self.userMalOut[msgSender] += newBalances.malRewards
            newBalances.malRewards = 0
        # Update account balances:
        self._updateAccountBalances(msgSender, oldBalances, newBalances)

    # --- View balances methods ---

    def getAccountBalances(self, _account):
        (_, newLastMalRewardPerAvailableCumS) = self._calculateMalRewardCumulativeSum(self.lastTotalMalRewards, self.lastMalRewardPerAvailableCumS)
        newBalances = self._calculateAccountBalances(self.accountBalances[_account], newLastMalRewardPerAvailableCumS)
        (lusdToStake, lusdStaked, _, shouldUnstake) = _unpackAccountStakeData(newBalances.lusdStakeData)
        lusdAvailable = lusdToStake + newBalances.lusdUnstaked
        malRewards = newBalances.malRewards
        if self.isEmergencyState:
            return (lusdAvailable + lusdStaked, 0, malRewards, lusdToStake + lusdStaked, False)
        return (lusdAvailable, lusdStaked, malRewards, lusdToStake, shouldUnstake)

    def getTotalBalances(self):
        return (self.totalLusd, 0 if self.isEmergencyState else self.totalLusdStaked)

    def getLastSnapshot(self):
        return self._buildSnapshot(self.lastMalRewardPerAvailableCumS, self.epoch)

    # --- Governance methods ---

    def startNewEpoch(self, e):
        (self.blockTimestamp) = (e.ts)
        assert not self.isEmergencyState
        # Mock reward and loss:
        (lusdReward, totalLusdStakedAfter) = self._mock_epoch_reward_and_loss(e)
        totalLusdStakedBefore = self.totalLusdStaked
        # Calculate amount to unstake taking into account compounding loss:
        lusdToUnstake = 0
        if totalLusdStakedBefore != 0:
            lusdToUnstake = totalLusdStakedAfter * self.totalLusdToUnstake // totalLusdStakedBefore
            self.lusdStabilityPool.withdrawFromSP(lusdToUnstake)
        # Calculate LUSD reward portion to unstake:
        lusdRewardToHold = 0
        if totalLusdStakedBefore != 0:
            newTotalLusdToUnstake = (totalLusdStakedAfter + lusdReward) * self.totalLusdToUnstake // totalLusdStakedBefore
            lusdRewardToHold = newTotalLusdToUnstake - lusdToUnstake
        # Stake LUSD to Stability Pool if needed:
        lusdToStake = self.totalLusdToStake + lusdReward - lusdRewardToHold
        if lusdToStake != 0:
            self.lusdStabilityPool.provideToSP(lusdToStake)
        # Calculate new total balances:
        newTotalLusd = self.totalLusd + lusdReward + totalLusdStakedAfter - totalLusdStakedBefore
        newTotalLusdStaked = totalLusdStakedAfter + lusdToStake - lusdToUnstake
        # Start new epoch:
        self._updateNewEpochData(lusdReward, totalLusdStakedBefore, totalLusdStakedAfter, newTotalLusd)
        # Update total balances:
        self.totalLusd = newTotalLusd
        self.totalLusdStaked = newTotalLusdStaked
        self.totalLusdToStake = 0
        self.totalLusdToUnstake = 0

    def emergencyWithdraw(self, e):
        (self.blockTimestamp) = (e.ts)
        assert not self.isEmergencyState
        self.isEmergencyState = True
        # Mock reward and loss:
        (lusdReward, totalLusdStakedAfter) = self._mock_epoch_reward_and_loss(e)
        totalLusdStakedBefore = self.totalLusdStaked
        # Withdraw everything from LUSD Stability Pool:
        if totalLusdStakedBefore != 0:
            self.lusdStabilityPool.withdrawFromSP(UINT256_MAX)
        # Calculate stake/unstake amounts:
        lusdToUnstake = 0
        lusdRewardToHold = 0
        if totalLusdStakedBefore != 0:
            lusdToUnstake = totalLusdStakedAfter * self.totalLusdToUnstake // totalLusdStakedBefore
            newTotalLusdToUnstake = (totalLusdStakedAfter + lusdReward) * self.totalLusdToUnstake // totalLusdStakedBefore
            lusdRewardToHold = newTotalLusdToUnstake - lusdToUnstake
        lusdToStake = self.totalLusdToStake + lusdReward - lusdRewardToHold
        # Calculate new total balances:
        newTotalLusd = self.totalLusd + lusdReward + totalLusdStakedAfter - totalLusdStakedBefore
        newTotalLusdStaked = totalLusdStakedAfter + lusdToStake - lusdToUnstake
        # Start new epoch:
        self._updateNewEpochData(lusdReward, totalLusdStakedBefore, totalLusdStakedAfter, newTotalLusd)
        # Update total balances:
        self.totalLusd = newTotalLusd
        self.totalLusdStaked = newTotalLusdStaked
        self.totalLusdToStake = 0
        self.totalLusdToUnstake = 0

    def emergencyRecover(self, e):
        (self.blockTimestamp) = (e.ts)
        assert self.isEmergencyState
        self.isEmergencyState = False
        # Update cumulative sums:
        self._updateMalRewardCumulativeSum()
        # Stake LUSD to Stability Pool:
        if self.totalLusdStaked != 0:
            self.lusdStabilityPool.provideToSP(self.totalLusdStaked)

    # --- Internal methods ---

    def _updateNewEpochData(self, _lusdReward, _totalLusdStakedBefore, _totalLusdStakedAfter, _totalLusd):
        epoch_ = self.epoch
        epochSnapshot = self.epochSnapshots[epoch_]
        # Calculate new MAL cumulative sums:
        newMalRewardPerAvailableCumS = self._updateMalRewardCumulativeSum()
        newMalRewardPerStakedCumS = epochSnapshot.malRewardPerStakedCumS + \
            (newMalRewardPerAvailableCumS - epochSnapshot.malRewardPerAvailableCumS) * epochSnapshot.lusdProfitFactorCumP // self.DECIMAL_PRECISION
        # Calculate new LUSD profit cumulative product:
        newLusdProfitFactorCumP = epochSnapshot.lusdProfitFactorCumP
        if _totalLusdStakedBefore != 0:
            newLusdProfitFactorCumP = newLusdProfitFactorCumP * (_lusdReward + _totalLusdStakedAfter) // _totalLusdStakedBefore
        if newLusdProfitFactorCumP == 0:
            self.previousResetEpoch[epoch_ + 1] = self.lastResetEpoch
            self.lastResetEpoch = epoch_ + 1
        # Save epoch snapshot:
        self.epochSnapshots[epoch_ + 1] = Snapshot(
            newLusdProfitFactorCumP,
            newMalRewardPerStakedCumS,
            newMalRewardPerAvailableCumS,
        )
        # Advance epoch:
        self.epoch = epoch_ + 1
        self.epochStartTime = self.blockTimestamp

    # --- Update state methods ---

    def _updateAccountBalances(self, _account, _oldBalances, _newBalances):
        if (_newBalances.lusdStakeData >> 32) == 0 and _newBalances.malRewards == 0 and _newBalances.lusdUnstaked == 0:
            self.accountBalances[_account] = AccountBalances()
            return
        if _oldBalances.lusdStakeData != _newBalances.lusdStakeData:
            self.accountBalances[_account].lusdStakeData = _newBalances.lusdStakeData
        if _oldBalances.malRewardPerAvailableCumS != _newBalances.malRewardPerAvailableCumS:
            self.accountBalances[_account].malRewardPerAvailableCumS = _newBalances.malRewardPerAvailableCumS
        if _oldBalances.malRewards != _newBalances.malRewards:
            self.accountBalances[_account].malRewards = _newBalances.malRewards
        if _oldBalances.lusdUnstaked != _newBalances.lusdUnstaked:
            self.accountBalances[_account].lusdUnstaked = _newBalances.lusdUnstaked

    def _updateMalRewardCumulativeSum(self):
        lastTotalMalRewards_ = self.lastTotalMalRewards
        lastMalRewardPerAvailableCumS_ = self.lastMalRewardPerAvailableCumS
        (newLastTotalMalRewards, newLastMalRewardPerAvailableCumS) = self._calculateMalRewardCumulativeSum(
            lastTotalMalRewards_, lastMalRewardPerAvailableCumS_
        )
        if lastTotalMalRewards_ != newLastTotalMalRewards:
            self.lastTotalMalRewards = newLastTotalMalRewards
        if lastMalRewardPerAvailableCumS_ != newLastMalRewardPerAvailableCumS:
            self.lastMalRewardPerAvailableCumS = newLastMalRewardPerAvailableCumS
        return newLastMalRewardPerAvailableCumS

    # --- Calculate state methods ---

    def _buildSnapshot(self, _malRewardPerAvailableCumS, _epoch):
        epochSnapshot = self.epochSnapshots[_epoch]
        return Snapshot(
            epochSnapshot.lusdProfitFactorCumP,
            epochSnapshot.malRewardPerStakedCumS + \
                (_malRewardPerAvailableCumS - epochSnapshot.malRewardPerAvailableCumS) * epochSnapshot.lusdProfitFactorCumP // self.DECIMAL_PRECISION,
            _malRewardPerAvailableCumS
        )

    def _calculateMalRewardCumulativeSum(self, _lastTotalMalRewards, _lastMalRewardsPerAvailableCumS):
        _newLastMalRewardsPerAvailableCumS = _lastMalRewardsPerAvailableCumS
        # Calculate MAL reward since last update:
        newUpdateTime = min(self.blockTimestamp, self.malDistributionEndTime)
        _newLastTotalMalRewards = self._calculateTotalMalRewards(newUpdateTime)
        malRewardSinceLastUpdate = _newLastTotalMalRewards - _lastTotalMalRewards
        if malRewardSinceLastUpdate == 0:
            return (_newLastTotalMalRewards, _newLastMalRewardsPerAvailableCumS)
        # Calculate new MAL cumulative sum:
        totalLusd_ = self.totalLusd
        if totalLusd_ != 0:
            _newLastMalRewardsPerAvailableCumS += malRewardSinceLastUpdate * self.DECIMAL_PRECISION // totalLusd_
        return (_newLastTotalMalRewards, _newLastMalRewardsPerAvailableCumS)

    def _calculateAccountBalances(self, _oldBalances, _newLastMalRewardPerAvailableCumS):
        epoch_ = self.epoch
        lastResetEpoch_ = self.lastResetEpoch
        (newLusdToStake, newLusdStaked, accountEpoch, shouldUnstake) = _unpackAccountStakeData(_oldBalances.lusdStakeData)
        newLusdUnstaked = _oldBalances.lusdUnstaked
        newMalRewards = _oldBalances.malRewards
        # Calculate account balances at the end of last account action epoch:
        fromSnapshot = self._buildSnapshot(_oldBalances.malRewardPerAvailableCumS, accountEpoch)
        if (accountEpoch != epoch_ and (newLusdToStake != 0 or shouldUnstake)):
            accountEpochSnapshot = self.epochSnapshots[accountEpoch + 1]
            (newLusdStaked, newMalRewards) = self._calculateAccountBalancesFromToSnapshots(
                newLusdUnstaked + newLusdToStake, newLusdStaked, newMalRewards, fromSnapshot, accountEpochSnapshot
            )
            if (lastResetEpoch_ != 0 and (accountEpoch + 1 == lastResetEpoch_ or self.previousResetEpoch[accountEpoch + 1] != 0)):
                newLusdStaked = 0
            # Perform adjustment:
            if (shouldUnstake):
                newLusdUnstaked += newLusdStaked
                newLusdStaked = 0
                shouldUnstake = False
            if (newLusdToStake != 0):
                newLusdStaked += newLusdToStake
                newLusdToStake = 0
            fromSnapshot = accountEpochSnapshot
        # Check practically impossible event of epoch reset:
        if (lastResetEpoch_ != 0 and lastResetEpoch_ > accountEpoch + 1):
            resetEpoch = lastResetEpoch_
            while (self.previousResetEpoch[resetEpoch] > accountEpoch + 1):
                resetEpoch = self.previousResetEpoch[resetEpoch]
            resetEpochSnapshot = self.epochSnapshots[resetEpoch]
            (newLusdStaked, newMalRewards) = self._calculateAccountBalancesFromToSnapshots(
                newLusdUnstaked + newLusdToStake, newLusdStaked, newMalRewards, fromSnapshot, resetEpochSnapshot
            )
            newLusdStaked = 0
            fromSnapshot = resetEpochSnapshot
        # Calculate account balance changes from fromSnapshot to lastSnapshot:
        lastSnapshot = self._buildSnapshot(_newLastMalRewardPerAvailableCumS, epoch_)
        (newLusdStaked, newMalRewards) = self._calculateAccountBalancesFromToSnapshots(
            newLusdUnstaked + newLusdToStake, newLusdStaked, newMalRewards, fromSnapshot, lastSnapshot
        )
        # New balances:
        _newBalances = AccountBalances()
        _newBalances.lusdStakeData = _packAccountStakeData(newLusdToStake, newLusdStaked, epoch_, shouldUnstake)
        _newBalances.malRewardPerAvailableCumS = _newLastMalRewardPerAvailableCumS
        _newBalances.malRewards = newMalRewards
        _newBalances.lusdUnstaked = newLusdUnstaked
        return _newBalances

    def _calculateAccountBalancesFromToSnapshots(self, _lusdAvailable, _lusdStaked, _malRewards, _fromSnapshot, _toSnapshot):
        _malRewardsAfter = _malRewards + \
            (_lusdStaked * (_toSnapshot.malRewardPerStakedCumS - _fromSnapshot.malRewardPerStakedCumS) // _fromSnapshot.lusdProfitFactorCumP) + \
            (_lusdAvailable * (_toSnapshot.malRewardPerAvailableCumS - _fromSnapshot.malRewardPerAvailableCumS) // self.DECIMAL_PRECISION)
        _lusdStakedAfter = _lusdStaked * _toSnapshot.lusdProfitFactorCumP // _fromSnapshot.lusdProfitFactorCumP
        return (_lusdStakedAfter, _malRewardsAfter)

    def _calculateTotalMalRewards(self, timestamp):
        F = self.malDecayFactor
        elapsedSecs = (timestamp - self.deploymentTime)
        if F == E18:
            return self.malRewardPerSecond * elapsedSecs
        decayT = self.malDecayPeriodSeconds
        epochs = elapsedSecs // decayT
        powF = self._calculateDecayPower(F, epochs)
        cumFraction = (self.DECIMAL_PRECISION - powF) * self.DECIMAL_PRECISION // (self.DECIMAL_PRECISION - F)
        _totalMalRewards = (self.malRewardPerSecond * cumFraction * decayT) // self.DECIMAL_PRECISION
        secs = elapsedSecs - decayT * epochs
        if secs != 0:
            _totalMalRewards += (self.malRewardPerSecond * powF * secs) // self.DECIMAL_PRECISION
        return _totalMalRewards

    def _calculateDecayPower(self, _f, _n):
        return GammaMath.decPow(_f, _n)

    # --- END OF GammaFarm logic ---

    def simulate_events(self, events):
        for e in events:
            self.simulate_event(e)
        return self.gather_state()

    def simulate_event(self, e):
        self.events_history.append(e)
        if self.debug:
            self.fout.write(f"=========\n* {e}\n")
        if e.user is not None:
            self.users.add(e.user)
        if e.type == EventType.DEPOSIT:
            self.deposit(e)
        elif e.type == EventType.WITHDRAW:
            self.withdraw(e)
        elif e.type == EventType.UNSTAKE:
            self.unstake(e)
        elif e.type == EventType.UNSTAKE_AND_WITHDRAW:
            self.unstakeAndWithdraw(e)
        elif e.type == EventType.CLAIM:
            self.claim(e)
        elif e.type == EventType.NEW_EPOCH:
            self.startNewEpoch(e)
        elif e.type == EventType.EMERGENCY_WITHDRAW:
            self.emergencyWithdraw(e)
        elif e.type == EventType.EMERGENCY_RECOVER:
            self.emergencyRecover(e)
        if self.debug:
            self.print_state()

    def print_state(self):
        lastSnapshot = self.getLastSnapshot()
        v = [
            f"V={self.totalLusd / E18d}",
            f"S={self.totalLusdStaked / E18d}",
            f"S_IN={self.totalLusdToStake / E18d}",
            f"S_OUT={self.totalLusdToUnstake / E18d}",
            f"P={lastSnapshot.lusdProfitFactorCumP / E18d}",
            f"S1={lastSnapshot.malRewardPerStakedCumS / E18d}",
            f"S2={lastSnapshot.malRewardPerAvailableCumS / E18d}",
            f"spCompoundedDeposit={self.lusdStabilityPool.getCompoundedLUSDDeposit() / E18d}",
            f"ts={self.blockTimestamp}"
        ]
        self.fout.write(f"  GLOBAL: {', '.join(v)}\n")
        for u in sorted(list(self.users)):
            (A, S, M, lusdToStake, shouldUnstake) = self.getAccountBalances(u)
            state_str = f"a={A / E18d}, s={S / E18d}, m={M / E18d}, s_in={lusdToStake / E18d}, s_out={shouldUnstake}, LUSD_in={self.userLusdIn[u] / E18d}, LUSD_out={self.userLusdOut[u] / E18d}, MAL_out={self.userMalOut[u] / E18d}"
            self.fout.write(f"  {u}: {state_str}\n")

    def gather_state(self):
        s = SimulationState()
        s.users = self.users
        for user in self.users:
            s.userLusdIn[user] = self.userLusdIn[user]
            s.userLusdOut[user] = self.userLusdOut[user]
            s.userMalOut[user] = self.userMalOut[user]
            (s.lusdAvailable[user], s.lusdStaked[user], s.malRewards[user], _, _) = self.getAccountBalances(user)
        (s.totalLusd, s.totalLusdStaked) = self.getTotalBalances()
        lastSnapshot = self.getLastSnapshot()
        s.P = lastSnapshot.lusdProfitFactorCumP
        s.S1 = lastSnapshot.malRewardPerStakedCumS
        s.S2 = lastSnapshot.malRewardPerAvailableCumS
        s.epoch = self.epoch
        s.totalUserLusdIn = sum(s.userLusdIn.values())
        s.totalUserLusdOut = sum(s.userLusdOut.values())
        s.totalMalSupply = self.malToDistribute
        s.totalMalOut = sum(s.userMalOut.values())
        s.totalLusdReward = self.totalLusdReward
        s.totalLusdSpLoss = self.totalLusdSpLoss
        s.spCompoundedDeposit = self.lusdStabilityPool.getCompoundedLUSDDeposit()
        s.farmLusdBalance = s.totalUserLusdIn + self.totalLusdReward - self.totalLusdSpLoss - s.totalUserLusdOut - s.spCompoundedDeposit
        s.farmMalBalance = self.malToDistribute - s.totalMalOut
        assert s.spCompoundedDeposit <= s.totalLusdStaked
        assert s.farmLusdBalance >= 0
        assert sum(s.malRewards.values()) + s.totalMalOut <= s.totalMalSupply
        assert sum(s.lusdAvailable.values()) + s.totalLusdStaked <= s.totalLusd
        assert sum(s.lusdStaked.values()) <= s.totalLusdStaked
        return s

    def get_total_balances(self):
        return self.getTotalBalances()

    def get_account_balances(self, user):
        return self.getAccountBalances(user)

    def get_events_history(self):
        return self.events_history

    def _mock_epoch_reward_and_loss(self, e):
        totalLusdStakedBefore = self.lusdStabilityPool.getCompoundedLUSDDeposit()
        (lusdReward, totalLusdStakedAfter) = e.data.get_epoch_results(totalLusdStakedBefore)
        self.lusdStabilityPool.setCompoundedLUSDDeposit(totalLusdStakedAfter)
        self.totalLusdReward += lusdReward
        self.totalLusdSpLoss += (totalLusdStakedBefore - totalLusdStakedAfter)
        return (lusdReward, totalLusdStakedAfter)
