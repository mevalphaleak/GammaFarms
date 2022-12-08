import React from 'react';
import { useContext, useMemo, createContext } from 'react';
import { Contract } from '@ethersproject/contracts';
import { useWallet } from 'contexts/wallet';
import { GAMMA_FARM_ADDRESS, MAL_STAKER_HELPER_ADDRESS, NFT_POSITIONS_MANAGER_ADDRESS, UNISWAP_V3_QUOTER_ADDRESS, UNISWAP_V3_STAKER_ADDRESS } from 'config';
import NFT_POSITIONS_MANAGER_ABI from 'abis/NonfungiblePositionManager.json'
import MAL_STAKER_HELPER_ABI from 'abis/MalTokenStakerHelper.json'
import GAMMA_FARM_ABI from 'abis/GammaFarm.json'
import UNISWAP_V3_STAKER_ABI from 'abis/UniswapV3Staker.json'
import UNISWAP_V3_QUOTER_ABI from 'abis/UniswapV3Quoter.json'

// ContractsContext: {
//   gammaFarmContract: Contract | null,
//   malStakerHelper: Contract | null,
//   nftPositionsManager: Contract | null,
//   uniswapV3Quoter: Contract | null,
//   uniswapV3Staker: Contract | null,
// }
const ContractsContext = createContext();

export const ContractsProvider = ({ children }) => {
  const { signer } = useWallet();

  const gammaFarmContract = useMemo(
    () =>
      !signer
        ? null
        : new Contract(
            GAMMA_FARM_ADDRESS,
            GAMMA_FARM_ABI,
            signer,
        ),
    [signer]
  )

  const malStakerHelper = useMemo(
    () =>
      !signer
        ? null
        : new Contract(
            MAL_STAKER_HELPER_ADDRESS,
            MAL_STAKER_HELPER_ABI,
            signer,
        ),
    [signer]
  )

  const nftPositionsManager = useMemo(
    () =>
      !signer
        ? null
        : new Contract(
            NFT_POSITIONS_MANAGER_ADDRESS,
            NFT_POSITIONS_MANAGER_ABI,
            signer,
        ),
    [signer]
  )

  const uniswapV3Staker = useMemo(
    () =>
      !signer
        ? null
        : new Contract(
            UNISWAP_V3_STAKER_ADDRESS,
            UNISWAP_V3_STAKER_ABI,
            signer,
        ),
    [signer]
  )

  const uniswapV3Quoter = useMemo(
    () =>
      !signer
        ? null
        : new Contract(
            UNISWAP_V3_QUOTER_ADDRESS,
            UNISWAP_V3_QUOTER_ABI,
            signer,
        ),
    [signer]
  )

  return (
    <ContractsContext.Provider
      value={{
        gammaFarmContract,
        nftPositionsManager,
        malStakerHelper,
        uniswapV3Quoter,
        uniswapV3Staker,
      }}
    >
      {children}
    </ContractsContext.Provider>
  );
};

export function useContracts() {
  const context = useContext(ContractsContext);
  if (!context) {
    throw new Error('Missing Contracts context');
  }
  const {
    gammaFarmContract,
    malStakerHelper,
    nftPositionsManager,
    uniswapV3Quoter,
    uniswapV3Staker,
  } = context;

  return {
    gammaFarmContract,
    malStakerHelper,
    nftPositionsManager,
    uniswapV3Quoter,
    uniswapV3Staker,
  };
}
