import { useState, useMemo, useEffect } from 'react';
import { Contract } from "@ethersproject/contracts";
import ERC20_CONTRACT_ABI from 'abis/ERC20.json';
import { useWallet } from 'contexts/wallet';
import { sleep } from 'utils/promise';
import { toBigNumber } from 'utils/bigNumber';

const useTokenInfo = (tokenAddress) => {
  const [balance, setBalance] = useState(toBigNumber('0'));
  const [decimals, setDecimals] = useState();
  const [symbol, setSymbol] = useState();
  const { address, signer } = useWallet();

  const contract = useMemo(
    () =>
      signer &&
      tokenAddress &&
      new Contract(tokenAddress, ERC20_CONTRACT_ABI, signer),
    [tokenAddress, signer]
  );

  useEffect(() => {
    if (!contract || !address) return;
    let isMounted = true;
    const unsubs = [() => {isMounted = false}];

    const onBalanceChange = async (from, to) => {
      if (from === address || to === address) {
        await sleep(500);
        const newBalance = await contract.balanceOf(address);
        if (!isMounted) return;
        setBalance(toBigNumber(newBalance));
      }
    };

    const load = async () => {
      if (!contract || !address) return;
      const [decimals, symbol, balance] = await Promise.all([
        contract.decimals(),
        contract.symbol(),
        contract.balanceOf(address),
      ]);
      if (!isMounted) return;
      setDecimals(decimals);
      setSymbol(symbol);
      setBalance(toBigNumber(balance));
    };

    const subscribe = () => {
      if (!contract) return;
      const transferEvent = contract.filters.Transfer();
      contract.on(transferEvent, onBalanceChange);
      unsubs.push(() => {
        contract.off(transferEvent, onBalanceChange);
      });
    };

    load();
    subscribe();

    return () => {unsubs.map((u) => u())};
  }, [contract, address]);

  return {
    symbol,
    decimals,
    balance,
  };
};

export default useTokenInfo;
