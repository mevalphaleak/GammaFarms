import React from 'react';
import { useContext, createContext } from 'react';
import { useSnackbar } from 'notistack';

// NotificationsContext: {
//   showTxNotification: (description: string, hash: string) => void;
//   showErrorNotification: (msg: any) => void;
//   showSuccessNotification: (title: string, message: string) => void;
//   tx: (
//     startNotification: string,
//     endNotification: string,
//     makeTx: () => { hash: string; wait: () => Promise<any> }
//   ) => void;
// }
const NotificationsContext = createContext();

export const NotificationsProvider = ({ children }) => {
  const { enqueueSnackbar } = useSnackbar();

  const showTxNotification = (description, hash) => {
    enqueueSnackbar(
      { type: 'tx', description, hash },
      {
        persist: true,
      }
    );
  };

  const showErrorNotification = (msg) => {
    enqueueSnackbar(
      {
        type: 'error',
        message: msg?.error?.message || msg.responseText || msg.message || msg,
      },
      {
        persist: true,
      }
    );
  };

  const showSuccessNotification = (title, message) => {
    enqueueSnackbar(
      {
        type: 'success',
        title,
        message,
      },
      {
        persist: true,
      }
    );
  };

  const tx = async (
    startNotification,
    endNotification,
    makeTx
  ) => {
    try {
      const { hash, wait } = await makeTx();
      showTxNotification(startNotification, hash);
      await wait();
      showTxNotification(endNotification, hash);
    } catch (e) {
      showErrorNotification(e);
      throw e;
    }
  };

  return (
    <NotificationsContext.Provider
      value={{
        showTxNotification,
        showErrorNotification,
        showSuccessNotification,
        tx,
      }}
    >
      {children}
    </NotificationsContext.Provider>
  );
};

export function useNotifications() {
  const context = useContext(NotificationsContext);
  if (!context) {
    throw new Error('Missing Notifications context');
  }
  const {
    showTxNotification,
    showErrorNotification,
    showSuccessNotification,
    tx,
} = context;
  return {
    showTxNotification,
    showErrorNotification,
    showSuccessNotification,
    tx,
  };
}