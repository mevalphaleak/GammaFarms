import React from 'react';
import {
  useState,
  useContext,
  useMemo,
  useEffect,
  createContext,
} from 'react';

import { INCENTIVE } from 'config';
import { useContracts } from 'contexts/contracts';
import { useWallet } from 'contexts/wallet';

// LiquidityPosition: { tokenId, owner, liquidity, isStaked, reward }
// Incentive: { id, reward, ended, key: { rewardToken, pool, startTime, endTime, refundee} }
// IncentiveStats: { totalRewardUnclaimed, totalSecondsClaimedX128, numberOfStakes }
// UniswapLiquidityDataContext: {
//   positions: LiquidityPosition[];
//   incentives: Incentive[];
//   incentiveStats: IncentiveStats | null;
// }
const UniswapLiquidityDataContext = createContext();

export const UniswapLiquidityDataProvider = ({ children }) => {
  const { uniswapV3Staker, nftPositionsManager, malStakerHelper } = useContracts();
  const { address, network } = useWallet();
  const [positions, setPositions] = useState([]);
  const [incentiveStats, setIncentiveStats] = useState();

  // Load incentives
  const incentive = useMemo(() => INCENTIVE, []);

  // Load incentive stats
  useEffect(() => {
    const loadInfo = async () => {
      if (!incentive || !uniswapV3Staker) return null;
      try {
        const stats = await uniswapV3Staker.incentives(incentive.id);
        setIncentiveStats(stats);
      } catch (_) {}
    }
    loadInfo();
  }, [uniswapV3Staker, incentive]);

  // Load owned and transfered positions
  useEffect(() => {
    if (!nftPositionsManager || !uniswapV3Staker) return;
    if (!address || !incentive) return;

    let isMounted = true;
    const unsubs = [() => {isMounted = false}];

    const loadPositionsWithHelper = async (owner) => {
      const positions = [];
      const result = await malStakerHelper.findAllValidPositions(owner);
      for (let i = 0; i < result.validTokenIds.length; i++) {
        const tokenId = result.validTokenIds[i];
        const liquidity = result.validTokenLiquidity[i];
        const tokenOwner = result.validTokenOwner[i];
        const tokenStakes = result.validTokenStakes[i];
        let reward = null;
        try {
          const rewardInfo = await uniswapV3Staker.getRewardInfo(
            incentive.key,
            tokenId
          );
          reward = rewardInfo.reward;
        } catch (_) {
        }
        positions.push({
          tokenId: Number(tokenId.toString()),
          owner: tokenOwner,
          liquidity,
          reward,
          isStaked: tokenStakes > 0,
        })
      }
      return positions;
    }

    const load = async () => {
      if (!malStakerHelper || !nftPositionsManager || !uniswapV3Staker) return
      if (!network || !address) return;

      let positions = [];
      positions = await loadPositionsWithHelper(address);
      positions.sort((a, b) => a.tokenId - b.tokenId);

      if (!isMounted) return;
      setPositions(positions);
    };

    load();

    return () => {unsubs.map((u) => u())};
  }, [
    network,
    address,
    nftPositionsManager,
    uniswapV3Staker,
    malStakerHelper,
    incentive,
  ]);

  useEffect(() => {
    if (!uniswapV3Staker || !incentive) return;
    let isMounted = true;
    const unsubs = [() => {isMounted = false}];

    const updateStaked = (tokenId, incentiveId) => {
      if (incentiveId !== incentive.id) return;
      if (!isMounted) return;
      setPositions((positions) =>
        positions.map((position) => {
          if (position.tokenId !== Number(tokenId.toString()))
            return position;
          position.isStaked = true;
          return position;
        })
      );
    };

    const updateUnstaked = (tokenId, incentiveId) => {
      if (incentiveId !== incentive.id) return;
      if (!isMounted) return;
      setPositions((positions) =>
        positions.map((position) => {
          if (position.tokenId !== Number(tokenId.toString()))
            return position;
          position.isStaked = false;
          return position;
        })
      );
    };

    const subscribe = () => {
      const stakedEvent = uniswapV3Staker.filters.TokenStaked();
      const unstakedEvent = uniswapV3Staker.filters.TokenUnstaked();

      uniswapV3Staker.on(stakedEvent, updateStaked);
      uniswapV3Staker.on(unstakedEvent, updateUnstaked);

      unsubs.push(() => {
        uniswapV3Staker.off(stakedEvent, updateStaked);
      });
      unsubs.push(() => {
        uniswapV3Staker.off(unstakedEvent, updateUnstaked);
      });
    };

    subscribe();

    return () => {unsubs.map((u) => u())};
  }, [uniswapV3Staker, positions, incentive]);

  return (
    <UniswapLiquidityDataContext.Provider
      value={{
        positions,
        incentive,
        incentiveStats,
      }}
    >
      {children}
    </UniswapLiquidityDataContext.Provider>
  );
};

export function useUniswapLiquidityData() {
  const context = useContext(UniswapLiquidityDataContext);
  if (!context) {
    throw new Error('Missing Data context');
  }
  const {
    positions,
    incentive,
    incentiveStats,
  } = context;

  return {
    positions,
    incentive,
    incentiveStats,
  };
}
