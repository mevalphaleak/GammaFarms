import React from 'react';
import {
  useCallback,
  useContext,
  useEffect,
  useState,
  createContext,
} from 'react';
import Decimal from 'decimal.js';

import { GAMMA_FARM_MAL_DISTRIBUTION_PERIOD, EPOCH_EVENTS_BATCH_SIZE, MAL_ADDRESS, USDC_ADDRESS, WETH_ADDRESS } from 'config';
import { useContracts } from 'contexts/contracts';
import { useWallet } from 'contexts/wallet';
import { E18 } from 'utils/bigNumber';

const SECONDS_IN_ONE_YEAR = 365 * 24 * 60 * 60;

const decPow = (a, n) => {
  const decMul = (x, y) => x.mul(y).add(E18.div(2)).div(E18);
  if (n === 0) { return E18; }
  let y = E18;
  let x = a;
  while (n > 1) {
    if (n % 2 === 0) {
      x = decMul(x, x);
      n = Math.floor(n / 2);
    } else {
      y = decMul(x, y);
      x = decMul(x, x);
      n = Math.floor((n - 1) / 2);
    }
  }
  return decMul(x, y);
}

const calculateTotalMalReward = (rewardRate, decayPeriod, decayFactor, elapsedSeconds) => {
  elapsedSeconds = Math.min(elapsedSeconds, GAMMA_FARM_MAL_DISTRIBUTION_PERIOD);
  let n = Math.floor(elapsedSeconds / decayPeriod);
  let fPow = decPow(decayFactor, n);
  let fCum = (E18.sub(fPow)).mul(E18).div(E18.sub(decayFactor));
  let m1 = rewardRate.mul(fCum).div(E18).mul(decayPeriod);
  let m2 = rewardRate.mul(fPow).div(E18).mul(elapsedSeconds - n * decayPeriod);
  let totalReward = m1.add(m2);
  return Decimal.div(totalReward.toString(), E18.toString());
}

const calculateMalReward = (rewardRate, decayPeriod, decayFactor, t1, t2) => {
  let total1 = calculateTotalMalReward(rewardRate, decayPeriod, decayFactor, t1);
  let total2 = calculateTotalMalReward(rewardRate, decayPeriod, decayFactor, t2);
  return total2.sub(total1);
}

const calculateLusdProfitFactorFromSnapshots = (snapshotA, snapshotB) => {
  const P_A = snapshotA?.lusdProfitFactorCumP || E18;
  const P_B = snapshotB.lusdProfitFactorCumP;
  const lusdProfitFactor = P_B.mul(E18).div(P_A);
  return Decimal.div(lusdProfitFactor.toString(), E18.toString());
}

const calculateLusdAnnualProfitFactorFromSnapshots = (snapshotA, snapshotB, n, t) => {
  const pf = calculateLusdProfitFactorFromSnapshots(snapshotA, snapshotB);
  const t_avg = t / n;
  const n_year = Math.floor(SECONDS_IN_ONE_YEAR / t_avg);  // expected number of epochs in a year
  const pf_year = pf.pow(n_year / n);  // expected yearly LUSD profit factor
  // For each 1 LUSD staked, user is expected to get "pf_year" LUSD after one year
  return pf_year.toNumber();
}

const calculateLusdProfitFactorSinceInception = async (immutables, epochState, lastSnapshot) => {
  const lastEpoch = epochState.epoch;
  const lastEpochStartTime = epochState.epochStartTime;
  const n = lastEpoch;  // number of epochs
  const t = lastEpochStartTime - immutables.deploymentTime;  // total duration of n epochs
  const pf = calculateLusdProfitFactorFromSnapshots(null, lastSnapshot, n, t);
  return pf.toNumber();
}

const calculateLusdAnnualProfitFactorLastNEpochs = async (signer, gammaFarm, epochState, lastSnapshot, n) => {
  // Calculate LUSD next year profit factor based on the last n epochs:
  const lastEpoch = epochState.epoch;
  const lastEpochStartTime = epochState.epochStartTime;
  if (lastEpoch <= n) {
    return null;
  }
  const fromEpoch = lastEpoch - n;
  const fromSnapshot = await gammaFarm.epochSnapshots(fromEpoch);
  const fromEpochStartTime = await getEpochStartTime(signer, gammaFarm, fromEpoch);
  const t = lastEpochStartTime - fromEpochStartTime;
  return calculateLusdAnnualProfitFactorFromSnapshots(fromSnapshot, lastSnapshot, n, t);
}

const getEpochStartTime = async (signer, gammaFarm, epoch) => {
  const epochStartedFilter = gammaFarm.filters.EpochStarted();
  const epochStartedEvents = await fetchEpochEvents(
    signer, epochStartedFilter, gammaFarm.interface, epoch
  );
  return epochStartedEvents[0].args.timestamp.toNumber();
}

const fetchEpochEvents = async (signer, filter, iface, epoch) => {
  let fromBlock = -EPOCH_EVENTS_BATCH_SIZE;
  let toBlock = null;
  let allEvents = [];
  while (allEvents.length === 0 || allEvents[0].args.epoch.toNumber() > epoch) {
    const logs = await signer.provider.getLogs({...filter, fromBlock, toBlock});
    const events = logs.map(log => iface.parseLog(log));
    events.sort((a, b) => a.args.epoch.toNumber() - b.args.epoch.toNumber());
    if (events && events.length > 0) {
      allEvents = [...events, ...allEvents];
    }
    toBlock = fromBlock - 1;
    fromBlock = fromBlock - EPOCH_EVENTS_BATCH_SIZE;
  }
  return allEvents.filter((e) => e.args.epoch.toNumber() >= epoch);
}

// APYInfo: {
//   APYLast7: {LUSD, Total} | null;
// }
// EpochState: {
//   isEmergencyState: bool | null;
//   epoch: number | null;
//   epochStartTime: number | null;
// }
// Immutables: {
//   deploymentTime: number,
//   malRewardPerSecond: BigNumber,
//   malDecayPeriodSeconds: BigNumber,
//   malDecayFactor: BigNumber,
// }
// FarmDataContext: {
//   balances: LiquidityPosition[];
//   epochState: EpochState;
//   APYInfo: APYInfo;
// }
const FarmDataContext = createContext();

export const FarmDataProvider = ({ children }) => {
  const { address, signer } = useWallet();
  const { gammaFarmContract, uniswapV3Quoter } = useContracts();

  const [balances, setBalances] = useState();
  const [epochState, setEpochState] = useState();
  const [immutables, setImmutables] = useState();

  const [malUsdPrice, setMalUsdPrice] = useState();
  const [APYInfo, setAPYInfo] = useState();

  const updateBalances = useCallback(async () => {
    if (!gammaFarmContract || !address) return;
    const [
      [availableLUSD, stakedLUSD, rewardsMAL, toStakeLUSD, shouldUnstakeLUSD],
      [totalBalanceLUSD, totalStakedLUSD],
    ] = await Promise.all([
      gammaFarmContract.getAccountBalances(address),
      gammaFarmContract.getTotalBalances(),
    ]);
    const balanceLUSD = availableLUSD.add(stakedLUSD);
    setBalances({
      balanceLUSD: balanceLUSD,
      availableLUSD: availableLUSD,
      stakedLUSD: stakedLUSD,
      rewardsMAL: rewardsMAL,
      toStakeLUSD: toStakeLUSD,
      shouldUnstakeLUSD: shouldUnstakeLUSD,
      totalStakedLUSD: totalStakedLUSD,
      totalBalanceLUSD: totalBalanceLUSD,
    });
  }, [gammaFarmContract, address]);

  const updateEpochState = useCallback(async () => {
    if (!gammaFarmContract) return;
    const [isEmergencyState, epoch, epochStartTime] = await Promise.all([
      gammaFarmContract.isEmergencyState(),
      gammaFarmContract.epoch(),
      gammaFarmContract.epochStartTime(),
    ]);
    setEpochState({
      isEmergencyState: isEmergencyState,
      epoch: epoch,
      epochStartTime: epochStartTime.toNumber(),
    });
  }, [gammaFarmContract]);

  const updateAPYInfo = useCallback(async () => {
    if (!signer || !gammaFarmContract || !balances || !immutables || !epochState || !malUsdPrice) return;

    // Get latest epoch snapshot:
    const lastEpoch = epochState.epoch;
    const lastSnapshot = await gammaFarmContract.getLastSnapshot();

    // First epoch or no LUSD was ever staked:
    if (lastEpoch === 0 || lastSnapshot.malRewardPerAvailableCumS.isZero()) {
      setAPYInfo({APYLast7: null});
      return;
    }

    // Calculate estimated total MAL reward next year:
    const nowTime = Math.max(Math.floor(Date.now()/1000), epochState.epochStartTime);
    const t1 = nowTime - immutables.deploymentTime;
    const t2 = t1 + SECONDS_IN_ONE_YEAR;
    const totalMal_year = calculateMalReward(
      immutables.malRewardPerSecond, immutables.malDecayPeriodSeconds, immutables.malDecayFactor, t1, t2
    );
    // Calculate projected next year MAL reward per LUSD (in USD):
    let malRewardPerLusdInUsd_year = 0;
    if (!totalMal_year.isZero()) {
      const totalLusd = Decimal.div(balances.totalBalanceLUSD.toString(), E18.toString());
      const malRewardPerLusd_year = totalMal_year.div(totalLusd.add(1));
      malRewardPerLusdInUsd_year = malRewardPerLusd_year.mul(malUsdPrice).toNumber();
    }
    // Calculate projected next year LUSD profit factor:
    const lusdProfitFactor_year = (lastEpoch <= 7)
      ? await calculateLusdProfitFactorSinceInception(immutables, epochState, lastSnapshot)
      : await calculateLusdAnnualProfitFactorLastNEpochs(signer, gammaFarmContract, epochState, lastSnapshot, 7);
    // Calculate APY:
    const lusdAPY = 100 * (lusdProfitFactor_year - 1);
    const totalAPY = 100 * (lusdProfitFactor_year + malRewardPerLusdInUsd_year - 1);
    setAPYInfo({
      APYLast7: {LUSD: lusdAPY, Total: totalAPY},
    });
  }, [signer, gammaFarmContract, balances, immutables, epochState, malUsdPrice]);

  const updateMalUsdPrice = useCallback(async () => {
    if (!uniswapV3Quoter) return;
    // Quote MAL price:
    const path = `${MAL_ADDRESS}000bb8${WETH_ADDRESS.substr(2)}0001f4${USDC_ADDRESS.substr(2)}`;
    const quotedMalUsdcPrice = await uniswapV3Quoter.callStatic.quoteExactInput(path, E18.toString());
    setMalUsdPrice(Decimal.div(quotedMalUsdcPrice.toString(), 1e6));
  }, [uniswapV3Quoter, setMalUsdPrice]);

  // Load balances:
  useEffect(() => { updateBalances(); }, [updateBalances]);
  // Load epoch state:
  useEffect(() => { updateEpochState(); }, [updateEpochState]);
  // Fetch MAL price:
  useEffect(() => { updateMalUsdPrice(); }, [updateMalUsdPrice]);
  // Load APY Info:
  useEffect(() => { updateAPYInfo(); }, [updateAPYInfo]);
  // Load immutables:
  useEffect(() => {
    const load = async () => {
      if (!gammaFarmContract) return null;
      const [
        deploymentTime,
        malRewardPerSecond,
        malDecayPeriodSeconds,
        malDecayFactor,
      ] = await Promise.all([
        gammaFarmContract.deploymentTime(),
        gammaFarmContract.malRewardPerSecond(),
        gammaFarmContract.malDecayPeriodSeconds(),
        gammaFarmContract.malDecayFactor(),
      ]);
      setImmutables({
        deploymentTime: deploymentTime.toNumber(),
        malRewardPerSecond,
        malDecayPeriodSeconds: malDecayPeriodSeconds.toNumber(),
        malDecayFactor,
      });
    }
    load();
  }, [gammaFarmContract]);

  return (
    <FarmDataContext.Provider
      value={{
        APYInfo,
        balances,
        epochState,
        malUsdPrice,
        updateBalances,
      }}
    >
      {children}
    </FarmDataContext.Provider>
  );
};

export function useFarmData() {
  const context = useContext(FarmDataContext);
  if (!context) {
    throw new Error('Missing Data context');
  }
  const {
    APYInfo,
    balances,
    epochState,
    malUsdPrice,
    updateBalances,
  } = context;

  return {
    APYInfo,
    balances,
    epochState,
    malUsdPrice,
    updateBalances,
  };
}