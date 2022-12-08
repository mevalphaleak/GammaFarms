import React from "react"
import { useMemo } from 'react';
import { Box, Dialog } from '@material-ui/core';
import { makeStyles } from '@material-ui/core/styles';
import { Close as Icon } from '@material-ui/icons';
import { useWallet } from 'contexts/wallet';
import { NETWORK_MAINNET } from "config";

const useStyles = makeStyles((theme) => ({
  container: {
    display: "flex",
    flexGrow: 1,
    flexDirection: "column",
    width: 450,
    padding: "0 20px 10px",
    lineHeight: "1.5rem",
    "& button": {
      width: "100%",
      padding: "10px 0",
      marginTop: 20,
      fontSize: 18,
    },
  },
  x: {
    position: "absolute",
    top: 5,
    right: 5,
    cursor: "pointer",
  },
  wallet: {
    display: "flex",
    alignItems: "center",
    cursor: "pointer",
    margin: "10px 0",
    "& img": {
      marginRight: 15,
    },
    "&:hover": {
      opacity: 0.8,
    },
  },
  wrongNetwork: {
    display: "flex",
    flexDirection: "column",
    textAlign: "center",
    justifyContent: "center",
    alignItems: "center",
  },
  wallets: {
    display: "flex",
    flexDirection: "column",
  },
}));

const ConnectWalletDialog = () => {
  const classes = useStyles();
  const wallet = useWallet();

  const isOnCorrectNetwork = useMemo(
    () => !wallet.network || wallet.network !== NETWORK_MAINNET,
    [wallet.network]
  );

  return (
    <Dialog
      onClose={() => {}}
      open={!isOnCorrectNetwork || wallet.isConnecting}
    >
      <div className={classes.container}>
        {isOnCorrectNetwork ? (
          <>
            <div className={classes.x}>
              <Icon style={{ fontSize: 20 }} onClick={wallet.stopConnecting} />
            </div>
            <h3>Connect Wallet</h3>
            <div className={classes.wallets}>
              <div
                onClick={wallet.connectMetamask}
                className={classes.wallet}
              >
                <img
                  src='wallets/metamask.svg'
                  width='35'
                  height='35'
                  alt='metamask'
                />
                <div>Metamask</div>
              </div>
            </div>
          </>
        ) : (
          <Box mt={2} className={classes.wrongNetwork}>
            <strong>
              Please connect to Ethereum Mainnet
            </strong>
            <div>or</div>
            <div style={{cursor: "pointer"}} onClick={wallet.disconnect}>
              disconnect
            </div>
          </Box>
        )}
      </div>
    </Dialog>
  );
};

export default ConnectWalletDialog;