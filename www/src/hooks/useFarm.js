import { useCallback, useState } from 'react';

import { useWallet } from 'contexts/wallet';
import { useContracts } from 'contexts/contracts';
import { useNotifications } from 'contexts/notifications';
import { useFarmData } from 'contexts/farm';
import { LUSD_ADDRESS } from 'config';
import { signPermitWithMetamask } from 'utils/signTypedData';

const useFarm = () => {
  const { tx } = useNotifications();
  const { address, signer } = useWallet();
  const { gammaFarmContract } = useContracts();

  const { updateBalances } = useFarmData();
  const [isDepositing, setIsDepositing] = useState(false);
  const [isUnstaking, setIsUnstaking] = useState(false);
  const [isWithdrawing, setIsWithdrawing] = useState(false);
  const [isClaiming, setIsClaiming] = useState(false);

  const deposit = useCallback(
    async (amount, onSuccess = () => {}) => {
      try {
        setIsDepositing(true);
        const nonceData = "0x7ecebe00000000000000000000000000" + address.substring(2);
        const params = [
          {'from': address, 'to': LUSD_ADDRESS, 'data': nonceData},
          'latest',
        ];
        const nonce = await signer.provider.send('eth_call', params);
        // const nonce = await lusdToken.nonces(address);
        const deadline = Date.now() + 3600;
        const signature = await signPermitWithMetamask({
          provider: signer.provider,
          name: "LUSD Stablecoin",
          version: "1",
          chainId: 1,
          verifyingContract: LUSD_ADDRESS,
          owner: address,
          spender: gammaFarmContract.address,
          nonce: nonce,
          deadline: deadline,
          value: amount,
        });
        const { r, s, v } = signature;
        const gasLimit = 200000;
        await tx('Depositing...', 'Deposited!', () =>
          gammaFarmContract.deposit(amount, deadline, v, r, s, {"gasLimit": gasLimit})
        );
        await updateBalances();
        onSuccess && onSuccess();
      } catch (e) {
        console.warn(e);
      } finally {
        setIsDepositing(false);
      }
    },
    [gammaFarmContract, signer, tx, updateBalances, address]
  );

  const withdraw = useCallback(
    async (onSuccess = () => {}) => {
      try {
        setIsWithdrawing(true);
        const gasLimit = 200000;
        await tx('Withdrawing...', 'Withdrew!', () =>
          gammaFarmContract.withdraw({"gasLimit": gasLimit})
        );
        await updateBalances();
        onSuccess && onSuccess();
      } catch (e) {
        console.warn(e);
      } finally {
        setIsWithdrawing(false);
      }
    },
    [gammaFarmContract, tx, updateBalances],
  );

  const unstake = useCallback(
    async (onSuccess = () => {}) => {
      try {
        setIsUnstaking(true);
        const gasLimit = 200000;
        await tx('Requesting unstake...', 'Unstake requested!', () =>
          gammaFarmContract.unstake({"gasLimit": gasLimit})
        );
        await updateBalances();
        onSuccess && onSuccess();
      } catch (e) {
        console.warn(e);
      } finally {
        setIsUnstaking(false);
      }
    },
    [gammaFarmContract, tx, updateBalances],
  );

  const unstakeAndWithdraw = useCallback(
    async (onSuccess = () => {}) => {
      try {
        setIsUnstaking(true);
        const gasLimit = 500000;
        await tx('Unstaking...', 'Unstaked and withdrawn!', () =>
          gammaFarmContract.unstakeAndWithdraw({"gasLimit": gasLimit})
        );
        await updateBalances();
        onSuccess && onSuccess();
      } catch (e) {
        console.warn(e);
      } finally {
        setIsUnstaking(false);
      }
    },
    [gammaFarmContract, tx, updateBalances],
  );

  const claim = useCallback(
    async (onSuccess = () => {}) => {
      try {
        setIsClaiming(true);
        const gasLimit = 200000;
        await tx('Claiming...', 'Claimed!', () =>
          gammaFarmContract.claim({"gasLimit": gasLimit})
        );
        await updateBalances();
        onSuccess && onSuccess();
      } catch (e) {
        console.warn(e);
      } finally {
        setIsClaiming(false);
      }
    },
    [gammaFarmContract, tx, updateBalances],
  );

  return {
    isDepositing,
    isWithdrawing,
    isUnstaking,
    isClaiming,
    deposit,
    withdraw,
    unstake,
    unstakeAndWithdraw,
    claim,
  };
};

export default useFarm;