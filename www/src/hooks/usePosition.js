import { useCallback, useState } from 'react';

import { useWallet } from 'contexts/wallet';
import { useContracts } from 'contexts/contracts';
import { useNotifications } from 'contexts/notifications';
import { useUniswapLiquidityData } from 'contexts/liquidity';

const usePosition = (tokenId) => {
  const { tx } = useNotifications();
  const { address } = useWallet();
  const { nftPositionsManager, uniswapV3Staker } = useContracts();
  const { incentive } = useUniswapLiquidityData();

  const [isWorking, setIsWorking] = useState(null);

  const approveAndTransfer = useCallback(
    async (onSuccess) => {
      if (!nftPositionsManager || !uniswapV3Staker || !incentive || !address) return;

      try {
        const approveCallData = nftPositionsManager.interface.encodeFunctionData(
          "approve",
          [uniswapV3Staker.address, tokenId]
        );
        const safeTransferFromCallData = nftPositionsManager.interface.encodeFunctionData(
          "safeTransferFrom(address,address,uint256)",
          [address, uniswapV3Staker.address, tokenId]
        );
        setIsWorking('Transfering...');
        await tx('Transfering...', 'Transfered!', () =>
          nftPositionsManager.multicall(
            [approveCallData, safeTransferFromCallData]
          )
        );
        onSuccess();
      } catch (_) {
      } finally {
        setIsWorking(null);
      }
    },
    [
      address,
      tokenId,
      incentive,
      uniswapV3Staker,
      nftPositionsManager,
      tx,
    ]
  );

  const stake = useCallback(
    async (onSuccess) => {
      if (!uniswapV3Staker || !incentive) return;

      try {
        setIsWorking('Staking...');
        await tx('Staking...', 'Staked!', () =>
          uniswapV3Staker.stakeToken(incentive.key, tokenId)
        );
        onSuccess();
      } catch (_) {
      } finally {
        setIsWorking(null);
      }
    },
    [tokenId, incentive, uniswapV3Staker, tx]
  );

  const unstakeAndWithdraw = useCallback(
    async (onSuccess) => {
      if (!uniswapV3Staker || !incentive || !address) return;

      try {
        setIsWorking('Withdrawing...');
        const unstakeCallData = uniswapV3Staker.interface.encodeFunctionData(
          "unstakeToken",
          [incentive.key, tokenId]
        );
        const withdrawCallData = uniswapV3Staker.interface.encodeFunctionData(
          "withdrawToken",
          [tokenId, address, new Uint8Array()]
        );
        const estimatedGasLimit = await uniswapV3Staker.estimateGas.multicall([unstakeCallData, withdrawCallData]);
        const gasLimit = Math.round(estimatedGasLimit.toNumber() * 1.5);
        await tx('Withdrawing...', 'Withdrew!', () =>
          uniswapV3Staker.multicall(
            [unstakeCallData, withdrawCallData],
            {"gasLimit": gasLimit},
          )
        );
        onSuccess();
      } catch (_) {
      } finally {
        setIsWorking(null);
      }
    },
    [address, tokenId, incentive, uniswapV3Staker, tx]
  );

  return { isWorking, approveAndTransfer, stake, unstakeAndWithdraw };
};

export default usePosition;
