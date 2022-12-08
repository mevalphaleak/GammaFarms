import React from "react"
import { HashRouter, Route, Switch } from 'react-router-dom';
import { Box, Container } from "@material-ui/core";

import { useWallet } from "contexts/wallet";
import Header from "components/Header";
import TabsBar from "components/TabsBar";
import FarmPage from 'components/farm/FarmPage';
import LandingPage from 'components/LandingPage';
import LiquidityPage from 'components/liquidity/LiquidityPage';

const Layout = () => {
  const { address } = useWallet();

  return (
    <HashRouter>
      <Header/>
      <Container maxWidth="lg">
        {address ? (
          <>
            <TabsBar/>
            <Box mt={1}>
              <Switch>
                <Route exact path="/" component={FarmPage} />
                <Route path="/farm" component={FarmPage} />
                <Route path="/lp/:action?/:tokenId?" component={LiquidityPage} />
              </Switch>
            </Box>
          </>
        ) : (
          <LandingPage/>
        )}
      </Container>
    </HashRouter>
  );
}

export default Layout;