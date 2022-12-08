import React from 'react';
import { makeStyles } from '@material-ui/core/styles';
import {
  Box,
  Button,
  Dialog,
  Typography,
} from "@material-ui/core";
import CloseIcon from '@material-ui/icons/Close';

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
  },
  dialogContent: {
    padding: 32,
    display: "flex",
    flex: 1,
    flexDirection: "column",
  },
  dialogForm: {
    padding: 16,
  }
}));


const FarmWithdrawDialog = ({
  isOpen,
  onClose,
  balances,
  withdraw,
  isWithdrawing,
}) => {
  const classes = useStyles();

  const close = () => {
    onClose();
  }

  const onWithdrawSubmit = () => {
    withdraw(() => close());
  }

  const { availableLUSD } = (balances || {});
  return (
    <Dialog open={isOpen} onClose={close}>
      <Box className={classes.container}>
        <Box px={4} mt={2} className={classes.dialogHeader}>
          <Typography variant='h5'>Withdraw</Typography>
          <CloseIcon className={classes.closeIcon} onClick={close} />
        </Box>

        <Box className={classes.dialogContent}>
          <Box pb={2}>
            <Typography variant="body2">
              You are about to withdraw your available LUSD balance.<br/>
              MAL rewards will be harvested automatically.
            </Typography>
          </Box>

          <Button disabled={isWithdrawing || !availableLUSD || availableLUSD.isZero()}
            size="large" color="primary" variant="contained" onClick={onWithdrawSubmit} fullWidth
          >
            {isWithdrawing ? "Withdrawing..." : "Withdraw"}
          </Button>
        </Box>
      </Box>
    </Dialog>
  );
};

export default FarmWithdrawDialog;
