import React from "react"
import { AppBar, Button, Container, Typography, Toolbar } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";
import { useWallet } from "contexts/wallet";

const useStyles = makeStyles((theme) => ({
  appbar: {
    boxShadow: 'none',
  },
  toolbar: {
    padding: 0,
  },
  titleRoot: {
    display: "flex",
    flexGrow: 1,
  },
  title: {
    display: "flex",
    alignItems: "center",
  },
  account: {
    marginRight: 10,
  },
  online: {
    backgroundColor: "#00ca72",
    width: 10,
    height: 10,
    borderRadius: 72,
  },
}));

const Header = () => {
  const classes = useStyles();
  const { address, startConnecting } = useWallet();
  const shortAddress =
    address && `${address.slice(0, 6)}...${address.slice(-4)}`;

  return (
    <AppBar className={classes.appbar} position="static">
      <Container maxWidth="lg">
        <Toolbar className={classes.toolbar}>
          <Typography variant="h6" className={classes.titleRoot}>
            <div className={classes.title}>GammaFarms</div>
          </Typography>
          {address ? (
            <>
              <span className={classes.online}/>
              &nbsp;
              <div className={classes.account}>
                {shortAddress}
              </div>
            </>
          ) : (
            <Button color="secondary" onClick={startConnecting}>
              Connect Wallet
            </Button>
          )}
        </Toolbar>
      </Container>
    </AppBar>
  );
}

export default Header;