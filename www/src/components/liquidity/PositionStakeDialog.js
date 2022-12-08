import React from 'react';
import { useState, useEffect } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import Box from '@material-ui/core/Box';
import Dialog from '@material-ui/core/Dialog';
import Typography from '@material-ui/core/Typography';
import Stepper from '@material-ui/core/Stepper';
import Step from '@material-ui/core/Step';
import StepLabel from '@material-ui/core/StepLabel';
import Button from '@material-ui/core/Button';
import CloseIcon from '@material-ui/icons/Close';

import { useContracts } from 'contexts/contracts';
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
  },
  dialogContent: {
    display: "flex",
    flex: 1,
    flexDirection: "column",
  },
  stepCompleted: {
    '& .MuiStepIcon-root.MuiStepIcon-completed': {
      'color': theme.palette.success.main,
    }
  }
}));

const STEPS = ['Transfer', 'Stake'];

const PositionStakeDialog = ({ isOpen, onClose, tokenId }) => {
  const classes = useStyles();
  const { nftPositionsManager, uniswapV3Staker } = useContracts();
  const { isWorking, approveAndTransfer, stake } = usePosition(parseInt(tokenId));
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    if (!uniswapV3Staker || !nftPositionsManager) return;

    const load = async () => {
      const owner = await nftPositionsManager.ownerOf(tokenId);
      if (owner === uniswapV3Staker.address) {
        setActiveStep(1);
      }
    };

    load();
  }, [tokenId, uniswapV3Staker, nftPositionsManager]);

  const approveAndTransferOrStake = () => {
    switch (activeStep) {
      case 0:
        return approveAndTransfer(() => setActiveStep(1));
      case 1:
        return stake(() => onClose());
      default:
        console.warn(`unknown step: ${activeStep}`);
    }
  };

  return (
    <Dialog open={isOpen} onClose={onClose}>
      <Box className={classes.container}>
        <Box px={4} mt={2} className={classes.dialogHeader}>
          <Typography variant='h5'>Stake #{tokenId}</Typography>
          <CloseIcon className={classes.closeIcon} onClick={() => onClose()} />
        </Box>

        <Stepper activeStep={activeStep}>
          {STEPS.map((label) => (
            <Step key={label}>
              <StepLabel className={classes.stepCompleted}>{label}</StepLabel>
            </Step>
          ))}
        </Stepper>

        <Box px={4}>
          {activeStep === 0 ?
            <div>
              First, we need to approve and transfer position before staking it.
              This can be done in a single transaction by clicking below.
            </div>
            : <div>
              You are about to stake your liquidity position and start earning rewards.
            </div>
          }
        </Box>

        <Box px={4} mb={2} mt={2}>
          <Button
            color='primary'
            variant='contained'
            onClick={approveAndTransferOrStake}
            disabled={isWorking != null}
          >
            {isWorking ? isWorking : STEPS[activeStep]}
          </Button>
        </Box>
      </Box>
    </Dialog>
  );
};

export default PositionStakeDialog;