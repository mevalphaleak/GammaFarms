import React from "react"
import { makeStyles } from "@material-ui/core/styles";
import { Button, Typography } from "@material-ui/core";

import ConnectWalletDialog from "components/ConnectWalletDialog"
import { useWallet } from "contexts/wallet";


const useStyles = makeStyles((theme) => ({
  contentRoot: {
    marginTop: 48,
  },
  bullets: {
    fontSize: "1.5rem",
  },
}));

export default function LandingPage() {
  const classes = useStyles();
  const { startConnecting } = useWallet();

  return (
    <>
      <div className={classes.contentRoot}>
        <Typography variant="h3">MAL Rewards Programs</Typography>
        <Typography variant="h6">by MEV Alpha Leak</Typography>
      </div>
      <div>
      <ul className={classes.bullets}>
        <li>Earn MAL tokens by depositing LUSD</li>
        <li>Earn MAL tokens from staking MAL/ETH liquidity on UniswapV3</li>
        <li>Withdraw rewards anytime</li>
      </ul>
      </div>
      <Button size="large" color="primary" variant="contained" onClick={startConnecting}>
        Connect Wallet
      </Button>
      <ConnectWalletDialog />
    </>
  );
}
