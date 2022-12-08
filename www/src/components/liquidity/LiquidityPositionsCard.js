import React, { useCallback } from "react"
import { makeStyles } from "@material-ui/core/styles";
import { Box, Button, Card, CardContent, Tooltip, Typography} from "@material-ui/core";
import { Table, TableBody, TableCell, TableHead, TableRow } from "@material-ui/core";
import InfoIcon from '@material-ui/icons/Info';

import { MAL_ADDRESS, WETH_ADDRESS } from "config";
import { useUniswapLiquidityData } from 'contexts/liquidity';
import { formatUnits } from 'utils/bigNumber';


const useStyles = makeStyles((theme) => ({
  card: {
    minHeight: 260,
  },
  cardTitle: {
    textAlign: "center",
    fontWeight: 500,
    marginBottom: 10,
  },
  stakeButtonCell: {
    width: 110,
    padding: 5,
  },
  stakeButton: {
    width: 100,
  },
  positionRewardBox: {
    display: "flex",
    alignItems: "center",
  },
  positionInfoIcon: {
    display: "flex",
    alignItems: "center",
    cursor: "pointer",
  },
  stakedIndicator: {
    backgroundColor: "#00ca72",
    width: 10,
    height: 10,
    borderRadius: 72,
  },
  stakedStatusCell: {
    width: 12,
    padding: 0,
  }
}));

const LiquidityPositionsCard = ({ history }) => {
  const classes = useStyles();
  const { positions } = useUniswapLiquidityData();

  return (
    <Card className={classes.card}>
      <CardContent>
        <Typography className={classes.cardTitle} variant="h5">
          UniswapV3 Liquidity Positions
        </Typography>

        <Typography>
          You have {positions.length} MAL-WETH liquidity positions
        </Typography>

        <Typography variant='caption'>
          Get {!positions.length ? 'some' : 'more'} by providing liquidity
          to MAL-WETH Pool{' '}
          <a
            href={`https://app.uniswap.org/#/add/${WETH_ADDRESS}/${MAL_ADDRESS}`}
            target='_blank'
            rel='noopener noreferrer'
          >
            here
          </a>
        </Typography>

        {!positions.length ? null : (
          <Box mt={2}>
            <Table aria-label='Positions' size={'small'}>
              <TableHead>
                <TableRow>
                  <TableCell align="left" className={classes.stakedStatusCell}></TableCell>
                  <TableCell>ID</TableCell>
                  <TableCell>Rewards</TableCell>
                  <TableCell
                    align='right'
                    className={classes.stakeButtonCell}
                  ></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {positions.map((position) => (
                  <LiquidityPositionTableRow
                    key={position}
                    {...{ position, history }}
                  />
                ))}
              </TableBody>
            </Table>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}

const LiquidityPositionTableRow = ({ position, history }) => {
  const classes = useStyles();

  const stake = useCallback(async () => {
    history.push(`/lp/stake/${position.tokenId}`);
  }, [position.tokenId, history]);

  const withdraw = useCallback(async () => {
    history.push(`/lp/withdraw/${position.tokenId}`);
  }, [position.tokenId, history]);

  return (
    <TableRow>
      <TableCell align="left" className={classes.stakedStatusCell}>
        {position.isStaked ?
          <Tooltip title="Staked">
            <div className={classes.stakedIndicator}/>
          </Tooltip>
          : null}
      </TableCell>
      <TableCell component='th' scope='row'>
        <a
          href={`https://app.uniswap.org/#/pool/${position.tokenId.toString()}`}
          target='_blank'
          rel='noopener noreferrer'
        >
          {position.tokenId.toString()}
        </a>
      </TableCell>
      <TableCell>
        {position.reward !== null ? (
          <Box className={classes.positionRewardBox}>
            <Box mr={1}>{formatUnits(position.reward, 18)}</Box>
            { !position.reward.isZero() ?
                <Tooltip
                  title='Withdraw position in order to claim accrued rewards'
                  placement='top'
                  arrow
                >
                  <Box className={classes.positionInfoIcon}>
                    <InfoIcon fontSize='small' />
                  </Box>
                </Tooltip>
                : null
            }
          </Box>
        ) : (
          '-'
        )}
      </TableCell>
      <TableCell align='right' className={classes.stakeButtonCell}>
        <Button
          size="small"
          color="primary"
          variant="contained"
          onClick={position.isStaked ? withdraw : stake}
          className={classes.stakeButton}
        >
          {position.isStaked ? 'Withdraw' : 'Stake'}
        </Button>
      </TableCell>
    </TableRow>
  );
}

export default LiquidityPositionsCard;