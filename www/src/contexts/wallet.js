import React from "react"
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Web3Provider } from "@ethersproject/providers";
import detectEthereumProvider from '@metamask/detect-provider'
import { IS_DEV, NETWORK_MAINNET, NETWORK_MAINNET_FORK } from "config";

const sendInjectedProviderRequest = async (method, params) => {
  if (!window.ethereum) throw new Error('No injected provider found');
  let response = null;
  if (window.ethereum.request) {
    response = await window.ethereum.request({method, params});
  } else if (window.ethereum.send) {
    response = await window.ethereum.send(method, params);
  } else {
    throw new Error('No injected provider send method found');
  }
  if (!response) {
    return response;
  }
  return response.hasOwnProperty('result') ? response.result : response;
}

// WalletContext: {
//   network: string | null,
//   signer: Signer | null,
//   address: string | null,
//   isConnecting: boolean,
//   startConnecting: () => void,
//   stopConnecting: () => void,
//   disconnect: () => void,
//   connectMetamask: () => void,
// }
const WalletContext = createContext();

export const WalletProvider = ({ children, loader }) => {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [walletState, setWalletState] = useState({
    address: null,
    network: null,
    signer: null,
  });

  const startConnecting = useCallback(() => setIsConnecting(true), [
    setIsConnecting,
  ]);
  const stopConnecting = useCallback(() => setIsConnecting(false), [
    setIsConnecting,
  ]);

  const activate = useCallback(async (web3Provider) => {
    web3Provider.on("accountsChanged", () => {
      window.location.reload();
    });
    web3Provider.on("chainChanged", () => {
      window.location.reload();
    });

    const provider = new Web3Provider(web3Provider);
    const networkInfo = await provider.getNetwork();
    let networkName = ~['homestead'].indexOf(networkInfo.name) ? NETWORK_MAINNET : networkInfo.name;
    if (IS_DEV && networkName === NETWORK_MAINNET) {
      const latestBlock = await provider.send('eth_getBlockByNumber', ['latest', false]);
      if (latestBlock.difficulty === '0x1') {
        networkName = NETWORK_MAINNET_FORK;
      }
    }

    const signer = provider.getSigner();
    setWalletState({
      address: await signer.getAddress(),
      network: networkName,
      signer: signer,
    });
    stopConnecting();
  }, [stopConnecting]);

  async function disconnect() {
    setWalletState({
      address: null,
      network: null,
      signer: null,
    });
  }

  const connectMetamask = useCallback(async () => {
    if (!window.ethereum) return;

    let accounts;
    // Try to connect using "eth_requestAccounts":
    try {
      accounts = await sendInjectedProviderRequest('eth_requestAccounts');
    } catch (error) {
      if (error.code === 4001 || error.code === -32002) {
        return;  // User rejected request or already pending
      }
    }

    // Try to connect using "enable":
    if (!accounts) {
      try {
        accounts = await window.ethereum.enable();
      } catch (error) {
        console.log("Unable to connect to provider", error);
        return;
      }
    }

    // Activate injected provider:
    if (accounts && accounts.length > 0) {
      await activate(window.ethereum);
    }
  }, [activate]);

  const activateIfAuthorized = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      const accounts = await sendInjectedProviderRequest('eth_accounts');
      if (accounts && accounts.length > 0) {
        await activate(window.ethereum);
      }
    } catch (_) {
    }
  }, [activate]);

  useEffect(() => {
    const load = async () => {
      if (isInitialized) return;
      const injectedWeb3Provider = await detectEthereumProvider();
      if (injectedWeb3Provider) {
        await activateIfAuthorized();
      }
      setIsInitialized(true);
    };
    load();
  }, [isInitialized, activateIfAuthorized]);

  if (!isInitialized) {
    return <>{loader}</>;
  }
  return (
    <WalletContext.Provider
      value={{
        network: walletState.network,
        signer: walletState.signer,
        address: walletState.address,
        isConnecting,
        startConnecting,
        stopConnecting,
        disconnect,
        connectMetamask,
      }}
    >
      {children}
    </WalletContext.Provider>
  );
};

export function useWallet() {
  const context = useContext(WalletContext);
  if (!context) {
    throw new Error("Missing wallet context");
  }
  const {
    network,
    signer,
    address,
    isConnecting,
    startConnecting,
    stopConnecting,
    disconnect,
    connectMetamask,
  } = context;

  return {
    network,
    signer,
    address,
    isConnecting,
    startConnecting,
    stopConnecting,
    disconnect,
    connectMetamask,
  };
}