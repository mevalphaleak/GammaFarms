import React from "react"
import { Box, Button, Card, CardContent, Tooltip } from "@material-ui/core";
import { Table, TableBody, TableCell, TableRow } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";
import LinkIcon from '@material-ui/icons/Link';

import { GAMMA_FARM_ADDRESS, MAL_ADDRESS } from "config";
import FarmEmergencyWarning from "components/farm/FarmEmergencyWarning";
import { useFarmData } from 'contexts/farm';
import { formatUnits } from "utils/bigNumber";

const useStyles = makeStyles((theme) => ({
  card: {
    minHeight: 260,
  },
  yourStatsTable: {
    "& .MuiTableCell-sizeSmall": {
      padding: "6px",
    },
  },
  sourceLink: {
    float: 'right',
  },
  farmDetailsTable: {
    "& .MuiTableCell-sizeSmall": {
      fontSize: 12,
    },
  },
  actionButtonCell: {
    width: 110,
  },
  actionButton: {
    width: 100,
  },
  stakeAdjustmentHint: {
    color: theme.palette.grey[600],
    fontSize: 12,
  },
  warningIcon: {
    color: theme.palette.warning.main,
  },
}));

const shortenAddress = (address) => `${address.slice(0, 6)}...${address.slice(-4)}`;

const FarmStatsCard = ({
  isWithdrawing,
  isUnstaking,
  isClaiming,
  claim,
  onWithdrawClick,
  onUnstakeClick,
}) => {
  const classes = useStyles();
  const { balances, epochState, APYInfo, malUsdPrice } = useFarmData();

  const onClaim = () => {
    claim(() => {});
  }

  const { availableLUSD, stakedLUSD, rewardsMAL, toStakeLUSD, shouldUnstakeLUSD, totalBalanceLUSD, totalStakedLUSD } = (balances || {});
  const { isEmergencyState } = (epochState || {});
  const { APYLast7 } = (APYInfo || {});
  const totalAPYLast7 = APYLast7 == null ? APYLast7 : APYLast7.Total;
  const lusdAPYLast7 = APYLast7 == null ? APYLast7 : APYLast7.LUSD;

  return (
    <Card className={classes.card}>
      <CardContent>
        <Box>
          <strong>Your Stats</strong>
          <Table className={classes.yourStatsTable} size="small">
            <TableBody>
              <TableRow>
                <TableCell>
                  <div>LUSD Available:</div>
                  <div className={classes.stakeAdjustmentHint}>
                    {toStakeLUSD && !toStakeLUSD.isZero() ? `${formatUnits(toStakeLUSD, 18, 2)} LUSD will be staked next epoch`: ''}
                  </div>
                </TableCell>
                <TableCell align="right">
                  {availableLUSD ? `${formatUnits(availableLUSD, 18, 2)} LUSD` : '-'}
                </TableCell>
                <TableCell className={classes.actionButtonCell} align="right">
                  <Button className={classes.actionButton} disabled={isWithdrawing || !availableLUSD || availableLUSD.isZero()}
                    size="small" color="primary" variant="contained" onClick={onWithdrawClick} fullWidth
                  >
                    Withdraw
                  </Button>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>
                  <div>LUSD Staked:</div>
                  <div className={classes.stakeAdjustmentHint}>
                    {shouldUnstakeLUSD ? `Full amount will be unstaked next epoch`: ''}
                  </div>
                </TableCell>
                <TableCell align="right">
                  {stakedLUSD ? `${formatUnits(stakedLUSD, 18, 2)} LUSD` : '-'}
                </TableCell>
                <TableCell className={classes.actionButtonCell} align="right">
                  <Button className={classes.actionButton} disabled={isUnstaking || shouldUnstakeLUSD || !stakedLUSD || stakedLUSD.isZero()}
                    size="small" color="primary" variant="contained" onClick={onUnstakeClick} fullWidth
                  >
                    Unstake
                  </Button>
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>MAL Rewards:</TableCell>
                <TableCell align="right">
                  {rewardsMAL ? `${formatUnits(rewardsMAL, 18, 2)} MAL` : '-'}
                </TableCell>
                <TableCell className={classes.actionButtonCell} align="right">
                  <Button className={classes.actionButton} disabled={isClaiming || !rewardsMAL || rewardsMAL.isZero()}
                    size="small" color="primary" variant="contained" onClick={onClaim} fullWidth
                  >
                    {isClaiming ? "Claiming..." : "Claim"}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>

        <Box mt={4}>
          <strong>Farm Details</strong>
          <div className={classes.sourceLink}>
            <Tooltip title="View source code on Etherscan">
              <a href={`https://etherscan.io/address/${GAMMA_FARM_ADDRESS}#code`} target='_blank' rel='noopener noreferrer'>
                <LinkIcon fontSize="small"/>
              </a>
            </Tooltip>
          </div>
          {isEmergencyState ? <FarmEmergencyWarning/> : null}
          <Table className={classes.farmDetailsTable} size="small">
            <TableBody>
              <TableRow>
                <TableCell>TVL:</TableCell>
                <TableCell align="right">
                  {totalBalanceLUSD ? `${formatUnits(totalBalanceLUSD, 18, 2)} LUSD` : '-'}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Total Staked:</TableCell>
                <TableCell align="right">
                  {totalStakedLUSD ? `${formatUnits(totalStakedLUSD, 18, 2)} LUSD` : '-'}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Total APY:</TableCell>
                <TableCell align="right">
                  {
                    totalAPYLast7 === undefined ? '-' : (
                      totalAPYLast7 === null ? 'too new' :
                      `${totalAPYLast7 > 0 ? "+" : ""}${totalAPYLast7.toFixed(2)} %`
                    )
                  }
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>LUSD APY:</TableCell>
                <TableCell align="right">
                  {
                    lusdAPYLast7 === undefined ? '-' : (
                      lusdAPYLast7 === null ? 'too new' :
                      `${lusdAPYLast7 > 0 ? "+" : ""}${lusdAPYLast7.toFixed(2)} %`
                    )
                  }
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>MAL Price:</TableCell>
                <TableCell align="right">
                  {!malUsdPrice ? '-' : `$${malUsdPrice.toFixed(2)}`}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>MAL Token:</TableCell>
                <TableCell align="right">
                  <a href={`https://etherscan.io/address/${MAL_ADDRESS}`} target='_blank' rel='noopener noreferrer'>
                    {shortenAddress(MAL_ADDRESS)}
                  </a>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>
      </CardContent>
    </Card>
  );
};

export default FarmStatsCard;