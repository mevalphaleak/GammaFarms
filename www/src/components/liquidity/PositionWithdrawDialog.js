import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Box from '@material-ui/core/Box';
import Dialog from '@material-ui/core/Dialog';
import Typography from '@material-ui/core/Typography';
import Button from '@material-ui/core/Button';
import CloseIcon from '@material-ui/icons/Close';

import usePosition from 'hooks/usePosition';

const useStyles = makeStyles((theme) => ({
  container: {
    [theme.breakpoints.up("sm")]: {
      width: 500,
    },
  },
  dialogHeader: {
    display: "flex",
    flexGrow: 1,
    justifyContent: "space-between",
    alignItems: "center",
  },
  closeIcon: {
    cursor: 'pointer',
  }
}));

const PositionWithdrawDialog = ({ isOpen, onClose, tokenId }) => {
  const classes = useStyles();
  const { isWorking, unstakeAndWithdraw } = usePosition(parseInt(tokenId));

  return (
    <Dialog open={isOpen} onClose={onClose}>
      <Box className={classes.container}>
        <Box px={4} mt={2} className={classes.dialogHeader}>
          <Typography variant='h5'>Withdraw #{tokenId}</Typography>
          <CloseIcon className={classes.closeIcon} onClick={() => onClose()} />
        </Box>

        <Box px={4} mt={2}>
          You are about to withdraw your liquidity position.
        </Box>

        <Box px={4} mb={2} mt={2}>
          <Button
            color='primary'
            variant='contained'
            onClick={() => unstakeAndWithdraw(() => onClose())}
            disabled={isWorking != null}
          >
            {isWorking ? isWorking : 'Withdraw'}
          </Button>
        </Box>
      </Box>
    </Dialog>
  );
};

export default PositionWithdrawDialog;
