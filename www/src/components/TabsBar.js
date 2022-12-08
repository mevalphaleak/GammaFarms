import React, { useEffect, useState } from "react"
import { useLocation, withRouter } from 'react-router-dom';
import { withStyles } from "@material-ui/core/styles";
import { Box, Tab, Tabs } from "@material-ui/core";

const StyledTabs = withStyles({
  indicator: {
    display: 'flex',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    '& > span': {
      maxWidth: 40,
      width: '100%',
      backgroundColor: '#635ee7',
    },
  },
})((props) => <Tabs {...props} TabIndicatorProps={{ children: <span /> }} />);

const StyledTab = withStyles((theme) => ({
  root: {
    textTransform: 'none',
    color: theme.palette.grey[600],
    fontWeight: theme.typography.fontWeightRegular,
    fontSize: theme.typography.pxToRem(15),
    marginRight: theme.spacing(1),
    '&:focus': {
      opacity: 1,
    },
  },
}))((props) => <Tab disableRipple {...props} />);

const TabsBar = ({ history }) => {
  const [tab, setTab] = useState("farm");
  const { pathname } = useLocation();

  const onSelectTab = (_, newTab) => {
    history.push(`/${newTab}`);
    setTab(newTab);
  }

  useEffect(() => {
    if (pathname.startsWith('/farm')) {
      setTab('farm');
    } else if (pathname.startsWith('/lp')) {
      setTab('lp');
    }
  }, [pathname]);

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <StyledTabs indicatorColor="primary" textColor="primary" value={tab} onChange={onSelectTab}>
        <StyledTab value="farm" label="Farm" />
        <StyledTab value="lp" label="LiquidityV3" />
      </StyledTabs>
    </Box>
  );
}

export default withRouter(TabsBar);