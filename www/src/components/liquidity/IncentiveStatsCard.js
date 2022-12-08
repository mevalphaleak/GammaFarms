import React from "react"
import { useState, useEffect } from "react";
import { makeStyles } from "@material-ui/core/styles";
import { Box, Button, Card, CardContent, Tooltip } from "@material-ui/core";
import { Table, TableBody, TableCell, TableRow } from "@material-ui/core";
import LinkIcon from '@material-ui/icons/Link';
import { BigNumber } from '@ethersproject/bignumber';
import moment from 'moment';

import { UNISWAP_V3_STAKER_ADDRESS } from "config";
import { useWallet } from 'contexts/wallet';
import { useContracts } from 'contexts/contracts';
import { useNotifications } from 'contexts/notifications';
import { useUniswapLiquidityData } from 'contexts/liquidity';
import { formatUnits } from 'utils/bigNumber';

const useStyles = makeStyles((theme) => ({
  card: {
    minHeight: 260,
  },
  sourceLink: {
    float: 'right',
  },
  yourStatsTable: {
    "& .MuiTableCell-sizeSmall": {
      padding: "6px",
    },
  },
  incentiveDetailsTable: {
    "& .MuiTableCell-sizeSmall": {
      fontSize: 12,
    },
  }
}));

const IncentiveStatsCard = () => {
  const classes = useStyles();
  const { uniswapV3Staker } = useContracts();
  const { incentive, incentiveStats } = useUniswapLiquidityData();
  const { address } = useWallet();
  const { tx } = useNotifications();

  const [reward, setReward] = useState(BigNumber.from(0));
  const [isClaiming, setIsClaiming] = useState(false);

  useEffect(() => {
    if (!uniswapV3Staker || !incentive || !address) return;
    let isMounted = true;
    const unsubs = [() => {isMounted = false}];

    const load = async () => {
      try {
        const rewardAmount = await uniswapV3Staker.rewards(incentive.key.rewardToken, address);
        if (!isMounted) return;
        setReward(rewardAmount);
      } catch (_) {}
    };

    const subscribe = () => {
      const tokenUnstakedEvent = uniswapV3Staker.filters.TokenUnstaked();
      uniswapV3Staker.on(tokenUnstakedEvent, load);
      unsubs.push(() => {
        uniswapV3Staker.off(tokenUnstakedEvent, load);
      });

      const rewardClaimedEvent = uniswapV3Staker.filters.RewardClaimed();
      uniswapV3Staker.on(rewardClaimedEvent, load);
      unsubs.push(() => {
        uniswapV3Staker.off(rewardClaimedEvent, load);
      });
    };

    load();
    subscribe();

    return () => {unsubs.map((u) => u())};
  }, [uniswapV3Staker, incentive, address]);

  const claim = async () => {
    if (!uniswapV3Staker || !incentive) return;

    try {
      setIsClaiming(true);
      const rewardAmount = await uniswapV3Staker.rewards(
        incentive.key.rewardToken,
        address
      );
      await tx('Claiming...', 'Claimed!', () =>
        uniswapV3Staker.claimReward(
          incentive.key.rewardToken,
          address,
          rewardAmount
        )
      );
    } catch (_) {
    } finally {
      setIsClaiming(false);
    }
  };

  const incentiveSecondsLeft = incentive ? incentive.key.endTime - Date.now() / 1000 : null;
  return (
    <Card className={classes.card}>
      <CardContent>
        <Box>
          <strong>Your Stats</strong>
          <Table className={classes.yourStatsTable} size="small">
            <TableBody>
              <TableRow>
                <TableCell>MAL Rewards:</TableCell>
                <TableCell align="right">
                  {reward ? formatTokenAmount(reward, 18, 'MAL') : '-'}
                </TableCell>
                <TableCell align="right">
                  <Button disabled={isClaiming || !reward || reward.isZero()}
                    size="small" color="primary" variant="contained" onClick={claim} fullWidth
                  >
                    {isClaiming ? "Claiming..." : "Claim"}
                  </Button>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>

        <Box mt={4}>
          <strong>Incentive Details</strong>
          <div className={classes.sourceLink}>
            <Tooltip title="View source code on Etherscan">
              <a href={`https://etherscan.io/address/${UNISWAP_V3_STAKER_ADDRESS}#code`} target='_blank' rel='noopener noreferrer'>
                <LinkIcon fontSize="small"/>
              </a>
            </Tooltip>
          </div>

          <Table className={classes.incentiveDetailsTable} size="small">
            <TableBody>
              <TableRow>
                <TableCell>Incentive ends:</TableCell>
                <TableCell align="right">
                  {incentive ?
                    <Tooltip
                      title={`~${moment.duration(incentiveSecondsLeft, 'seconds').humanize()} left`}
                      arrow
                      placement='top'
                    >
                      <div>{formatTimestamp(incentive.key.endTime)}</div>
                    </Tooltip>
                  : null}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Number of stakes:</TableCell>
                <TableCell align="right">
                  {incentiveStats ? incentiveStats.numberOfStakes.toString() : null}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell>Rewards unclaimed:</TableCell>
                <TableCell align="right">
                  {incentiveStats
                    ? formatTokenAmount(incentiveStats.totalRewardUnclaimed, 18, 'MAL')
                    : null
                  }
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Box>
      </CardContent>
    </Card>
  );
};

function formatTokenAmount(amount, decimals, symbol) {
  return `${formatUnits(amount, decimals)} ${symbol}`;
}

function formatTimestamp(unixtime) {
  return moment.unix(unixtime).local().format('YYYY-MM-DD HH:mm');
}

export default IncentiveStatsCard;