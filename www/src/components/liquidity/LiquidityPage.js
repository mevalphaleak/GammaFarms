import React, { useEffect, useState } from "react"
import { withRouter } from 'react-router-dom';
import { Box } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";

import IncentiveStatsCard from 'components/liquidity/IncentiveStatsCard';
import LiquidityPositionsCard from "components/liquidity/LiquidityPositionsCard";
import PositionStakeDialog from 'components/liquidity/PositionStakeDialog';
import PositionWithdrawDialog from 'components/liquidity/PositionWithdrawDialog';

const useStyles = makeStyles((theme) => ({
  cardBox: {
    padding: "12px",
    display: "flex",
    flex: 1,
    flexDirection: "column",
  }
}));

const LiquidityPage = ({
  match: { params: { action, tokenId } },
  history,
}) => {
  const classes = useStyles();
  const [isStakeDialogOpen, setIsStakeDialogOpen] = useState(false);
  const [isWithdrawDialogOpen, setIsWithdrawDialogOpen] = useState(false);

  useEffect(() => {
    if (!tokenId) return;
    if (action === 'stake') {
      setIsStakeDialogOpen(true);
    } else if (action === 'withdraw') {
      setIsWithdrawDialogOpen(true);
    }
  }, [tokenId, action]);

  const onStakeDialogClose = () => {
    setIsStakeDialogOpen(false);
    history.push('/lp');
  }

  const onWithdrawDialogClose = () => {
    setIsWithdrawDialogOpen(false);
    history.push('/lp');
  }

  return (
    <>
      <Box display={{ md: "flex" }}>
        <Box className={classes.cardBox}>
          <LiquidityPositionsCard {...{history}}/>
        </Box>
        <Box maxWidth={400} className={classes.cardBox}>
          <IncentiveStatsCard/>
        </Box>
      </Box>
      {
        tokenId ? (
          <>
            <PositionStakeDialog tokenId={tokenId} isOpen={isStakeDialogOpen} onClose={onStakeDialogClose}/>
            <PositionWithdrawDialog tokenId={tokenId} isOpen={isWithdrawDialogOpen} onClose={onWithdrawDialogClose}/>
          </>
        ) : null
      }
    </>
  );
}

export default withRouter(LiquidityPage);