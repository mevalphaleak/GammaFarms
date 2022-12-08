import React from "react"
import { makeStyles } from '@material-ui/core/styles';
import { Backdrop, CircularProgress, CssBaseline, ThemeProvider } from "@material-ui/core";
import { SnackbarProvider } from "notistack";
import theme from "./theme"

import Layout from "components/Layout";
import Notification from "components/Notification";
import { ContractsProvider } from "contexts/contracts";
import { UniswapLiquidityDataProvider } from "contexts/liquidity";
import { FarmDataProvider } from "contexts/farm";
import { NotificationsProvider } from "contexts/notifications";
import { WalletProvider } from "contexts/wallet";

const useStyles = makeStyles((theme) => ({
  snackbar: {
    top: 70,
  },
}));

export default function App() {
  const classes = useStyles();

  const loader = (
    <Backdrop
      sx={{ color: '#fff', zIndex: (theme) => theme.zIndex.drawer + 1 }}
      open={true}
    >
      <CircularProgress color="inherit" />
    </Backdrop>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline/>
      <WalletProvider {...{loader}}>
        <SnackbarProvider
          classes={{ root: classes.snackbar }}
          maxSnack={4}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          content={(key, data) => <div><Notification id={key} notification={data}/></div>}
        >
          <NotificationsProvider>
            <ContractsProvider>
              <FarmDataProvider>
                <UniswapLiquidityDataProvider>
                  <Layout/>
                </UniswapLiquidityDataProvider>
              </FarmDataProvider>
            </ContractsProvider>
          </NotificationsProvider>
        </SnackbarProvider>
      </WalletProvider>
    </ThemeProvider>
  )
}