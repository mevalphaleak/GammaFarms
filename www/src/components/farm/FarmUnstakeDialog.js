import React from 'react';
import { useState } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import { Box, Button, Checkbox, Dialog, Typography } from "@material-ui/core";
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
    padding: "16px 32px",
    display: "flex",
    flex: 1,
    flexDirection: "column",
  },
  unstakeAndWithdraw: {
    backgroundColor: theme.palette.error.main,
    color: "#fff",
    '&:hover': {
      backgroundColor: theme.palette.error.dark,
    },
  },
  unstakeOptionsLabel: {
    color: "gray",
    textDecoration: "underline",
    cursor: "pointer",
  },
  understandRisksLabel: {
    cursor: "pointer",
  }
}));

const FarmUnstakeDialog = ({
  isOpen,
  onClose,
  balances,
  unstake,
  unstakeAndWithdraw,
  isUnstaking,
}) => {
  const classes = useStyles();
  const [showUnstakeAndWithdraw, setShowUnstakeAndWithdraw] = useState(false);
  const [userUnderstandsRisk, setUserUnderstandsRisk] = useState(false);

  const close = () => {
    setShowUnstakeAndWithdraw(false);
    setUserUnderstandsRisk(false);
    onClose();
  }

  const onUnstakeSubmit = () => {
    unstake(() => close());
  }

  const onUnstakeAndWithdrawSubmit = () => {
    unstakeAndWithdraw(() => close());
  }

  const toggleShowUnstakeAndWithdraw = () => {
    if (isUnstaking) {
      return;
    }
    setUserUnderstandsRisk(false);
    setShowUnstakeAndWithdraw(!showUnstakeAndWithdraw);
  }

  const toggleUserUnderstandsRisk = (x, y) => {
    if (isUnstaking) {
      return;
    }
    setUserUnderstandsRisk(!userUnderstandsRisk);
  }

  const { stakedLUSD } = (balances || {});
  return (
    <Dialog open={isOpen} onClose={close}>
      <Box className={classes.container}>
        <Box px={4} mt={2} className={classes.dialogHeader}>
          <Typography variant='h5'>Unstake</Typography>
          <CloseIcon className={classes.closeIcon} onClick={close} />
        </Box>

        <Box className={classes.dialogContent}>
          <Box pb={2}>
            {!showUnstakeAndWithdraw
              ? <Typography variant="body2">
                  You are about to request an unstake of your staked LUSD balance.<br/>
                  This is not an instant action and will be performed when the new epoch starts: your "Staked" balance will{' '}
                  be moved to "Available" balance which you'll be able to withdraw in a separate transaction.<br/>
                  LUSD reward earned during current epoch will be unstaked as well.<br/>
                </Typography>
              : <div>
                  <Typography variant="body2">
                    If you don't want to wait until the next epoch, you can unstake and withdraw in a single transaction, <strong>however</strong>:
                  </Typography>
                  <ul>
                    <li>You will pay about x2 more in transaction fees</li>
                    <li>You will lose LUSD reward earned during current epoch</li>
                    <li>[!] If there were liquidations absorbed by LUSD Stability Pool during current epoch - you will likely receive less{' '}
                    than your shown staked balance and potentially may lose the whole balance</li>
                  </ul>
                  <span className={classes.understandRisksLabel} onClick={toggleUserUnderstandsRisk}>
                    <Checkbox color="primary" disabled={isUnstaking} checked={userUnderstandsRisk}/>
                    <span>I understand the risks</span>
                  </span>
                </div>
            }
          </Box>

          <Box>
            <Box>
              {!showUnstakeAndWithdraw
                ? <Button disabled={isUnstaking || !stakedLUSD || stakedLUSD.isZero()}
                    size="large" color="primary" variant="contained" onClick={onUnstakeSubmit} fullWidth
                  >
                    Request unstake
                  </Button>
                : <Button className={classes.unstakeAndWithdraw} disabled={isUnstaking || !userUnderstandsRisk || !stakedLUSD || stakedLUSD.isZero()}
                    size="large" variant="contained" onClick={onUnstakeAndWithdrawSubmit} fullWidth
                  >
                    Unstake and withdraw now
                  </Button>
              }
            </Box>
          </Box>

          <Box pt={2}>
            <span className={classes.unstakeOptionsLabel} onClick={toggleShowUnstakeAndWithdraw}>
              {!showUnstakeAndWithdraw
                ? "I can't wait and need my funds now"
                : "Take me back to the regular unstake option"
              }
            </span>
          </Box>
        </Box>
      </Box>
    </Dialog>
  );
};

export default FarmUnstakeDialog;
