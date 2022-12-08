import React, { useState } from "react"
import { Box } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";

import FarmDepositCard from "components/farm/FarmDepositCard";
import FarmStatsCard from "components/farm/FarmStatsCard";
import FarmWithdrawDialog from "components/farm/FarmWithdrawDialog";
import FarmUnstakeDialog from "components/farm/FarmUnstakeDialog";
import { useFarmData } from 'contexts/farm';
import useFarm from "hooks/useFarm";

const useStyles = makeStyles((theme) => ({
  cardBox: {
    padding: "12px",
    display: "flex",
    flex: 1,
    flexDirection: "column",
  }
}));

export default function FarmPage() {
  const classes = useStyles();
  const [isWithdrawDialogOpen, setIsWithdrawDialogOpen] = useState(false);
  const [isUnstakeDialogOpen, setIsUnstakeDialogOpen] = useState(false);
  const { balances, epochState, APYInfo } = useFarmData();
  const {
    isDepositing,
    isWithdrawing,
    isUnstaking,
    isClaiming,
    deposit,
    withdraw,
    unstake,
    unstakeAndWithdraw,
    claim,
  } = useFarm();

  return (
    <>
      <Box display={{ md: "flex" }}>
        <Box className={classes.cardBox}>
          <FarmDepositCard
            deposit={deposit}
            isDepositing={isDepositing}
          />
        </Box>
        <Box className={classes.cardBox}>
          <FarmStatsCard
            balances={balances}
            epochState={epochState}
            APYInfo={APYInfo}
            claim={claim}
            isWithdrawing={isWithdrawing}
            isUnstaking={isUnstaking}
            isClaiming={isClaiming}
            onWithdrawClick={() => setIsWithdrawDialogOpen(true)}
            onUnstakeClick={() => setIsUnstakeDialogOpen(true)}
          />
        </Box>
      </Box>

      <FarmWithdrawDialog
        isOpen={isWithdrawDialogOpen}
        onClose={() => setIsWithdrawDialogOpen(false)}
        balances={balances}
        epochState={epochState}
        withdraw={withdraw}
        isWithdrawing={isWithdrawing}
      />
      <FarmUnstakeDialog
        isOpen={isUnstakeDialogOpen}
        onClose={() => setIsUnstakeDialogOpen(false)}
        balances={balances}
        unstake={unstake}
        unstakeAndWithdraw={unstakeAndWithdraw}
        isUnstaking={isUnstaking}
      />
    </>
  );
}