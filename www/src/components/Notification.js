import React from 'react';
import clsx from 'clsx';
import { useMemo } from 'react';
import { makeStyles } from '@material-ui/core/styles';
import { Paper } from '@material-ui/core';
import {
  ArrowUpward as TxIcon,
  Done as SuccessIcon,
  Clear as ErrorIcon,
  Close as CloseIcon,
} from '@material-ui/icons';
import { useSnackbar } from 'notistack';
import { useWallet } from 'contexts/wallet';
import { NETWORK_MAINNET } from 'config';

const useStyles = makeStyles((theme) => ({
  paper: {
    color: 'white',
  },
  container: {
    padding: '10px 20px 10px 10px',
    display: "flex",
    flexGrow: 1,
    alignItems: "center",
    '& a': {
      color: 'white',
      display: 'block',
      textDecoration: 'underline',
    },
  },
  contentContainer: {
    display: "flex",
    flexGrow: 1,
    flexDirection: "column",
    justifyContent: "center",
  },
  icon: {
    marginRight: 10,
    display: 'inline-flex',
  },
  close: {
    position: 'absolute',
    top: 5,
    right: 5,
    cursor: 'pointer',
  },
  tx: {
    background: '#2196f3',
  },
  error: {
    background: '#d32f2f',
  },
  success: {
    background: '#43a047',
  },
  small: {
    fontSize: 12,
  },
}));

const Notification = ({id, notification}) => {
  const classes = useStyles();
  const { closeSnackbar } = useSnackbar();
  const clearNotification = () => closeSnackbar(id);

  const TYPES = {
    'tx': [TxIcon, TxContent],
    'error': [ErrorIcon, ErrorContent],
    'success': [SuccessIcon, SuccessContent],
  };

  const [, Content] = TYPES[notification.type];

  const notificationClass = useMemo(() => {
    const c = {
      tx: classes.tx,
      error: classes.error,
      success: classes.success,
    };
    return c[notification.type];
  }, [notification.type, classes.error, classes.success, classes.tx]);

  return (
    <Paper className={clsx(classes.paper, notificationClass)}>
      <div className={classes.close} onClick={clearNotification}>
        <CloseIcon style={{ fontSize: 15 }} />
      </div>
      <div className={classes.container}>
        <div className={classes.contentContainer}>
          <Content {...{ notification }} />
        </div>
      </div>
    </Paper>
  );
};

const TxContent = ({ notification }) => {
  const classes = useStyles();
  const { network } = useWallet();

  const isMainnet = network === NETWORK_MAINNET;

  return (
    <>
      <strong className={classes.small}>{notification.description}</strong>
      <a
        href={`https://${isMainnet ? '' : `${network}.`}etherscan.io/tx/${
          notification.hash
        }`}
        target='_blank'
        rel='noopener noreferrer'
        className={classes.small}
      >
        View on EtherScan
      </a>
    </>
  );
};

const ErrorContent = ({ notification }) => {
  const classes = useStyles();
  return (
    <>
      <strong className={clsx(classes.small, classes.error)}>
        {notification.message}
      </strong>
    </>
  );
};

const SuccessContent = ({ notification }) => {
  const classes = useStyles();
  return (
    <>
      <div>{notification.title}</div>
      <strong className={clsx(classes.small, classes.success)}>
        {notification.message}
      </strong>
    </>
  );
};

export default Notification;