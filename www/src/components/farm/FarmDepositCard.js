import React, { useState } from "react"
import {
  Box,
  Button,
  Card,
  CardContent,
  FormGroup,
  InputAdornment,
  TextField,
  Typography,
} from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";

import NumberFormat from 'react-number-format';
import { BigNumber } from '@ethersproject/bignumber';

import { LUSD_ADDRESS } from "config";
import useTokenInfo from "hooks/useTokenInfo";
import { formatUnits } from "utils/bigNumber";

const useStyles = makeStyles((theme) => ({
  card: {
    minHeight: 260,
  },
  cardTitle: {
    textAlign: "center",
    fontWeight: 500,
    marginBottom: 10,
  },
  form: {
    padding: 16,
  },
  availableBalance: {
    color: theme.palette.grey[600],
    fontSize: 12,
    padding: '0 12px',
  }
}));

function NumberFormatCustom(props) {
  const { inputRef, onChange, ...other } = props;

  return (
    <NumberFormat
      {...other}
      getInputRef={inputRef}
      onValueChange={(values) => {
        // {formattedValue: "12,345.67", value: "12345.67", floatValue: 12345.67}
        onChange({
          target: {
            name: props.name,
            value: values.value,
          },
        });
      }}
      isNumericString={true}
      allowLeadingZeros={false}
      allowNegative={false}
      decimalScale={18}
    />
  );
}

const FarmDepositCard = ({ isDepositing, deposit }) => {
  const classes = useStyles();
  const lusdInfo = useTokenInfo(LUSD_ADDRESS);
  const [depositInput, setDepositInput] = useState('');

  const onDepositInputChange = (event) => {
    setDepositInput(event.target.value);
  }

  const onDepositSubmit = () => {
    const v = inputToBigInt(depositInput);
    deposit(v, () => setDepositInput(''));
  }

  const inputToBigInt = (inputValue) => {
    let [i, f] = inputValue.replace(',', '').split('.');
    i = i || "0";
    f = (f || "0").substring(0, 18);
    f = f + "0".repeat(18 - f.length);
    return BigNumber.from(i + f).toBigInt();
  }

  const onBalanceClick = () => {
    if (!lusdInfo) return;
    let [i, f] = formatUnits(lusdInfo.balance, 18, 18).split('.');
    f = (f || "0").replace(/0+$/g, "");
    let v = i;
    if (f) {
      v += "." + f;
    }
    setDepositInput(v);
  }

  return (
    <Card className={classes.card}>
      <CardContent>
        <Typography className={classes.cardTitle} variant="h5">
          Deposit
        </Typography>

        <Typography variant="body2">
          You can earn LUSD and MAL rewards by depositing LUSD
        </Typography>

        <Box className={classes.form}>
          <FormGroup>
            <TextField
              label="Amount"
              name="depositInput"
              id="depositInput"
              variant="outlined"
              margin="dense"
              value={depositInput}
              onChange={onDepositInputChange}
              InputProps={{
                inputComponent: NumberFormatCustom,
                endAdornment: <InputAdornment position="end">LUSD</InputAdornment>,
              }}
            />
            { lusdInfo ? (
                <span className={classes.availableBalance}>
                  Available balance:{' '}
                  <span style={{'cursor': 'pointer'}} onClick={onBalanceClick}>
                    {formatUnits(lusdInfo.balance, 18, 2)}{' LUSD'}
                  </span>
                </span>
              ) : null
            }
          </FormGroup>
        </Box>

        <Button disabled={isDepositing || !depositInput || !inputToBigInt(depositInput)} size="large" color="primary" variant="contained" onClick={onDepositSubmit} fullWidth>
          {isDepositing ? "Depositing..." : "Deposit"}
        </Button>
      </CardContent>
    </Card>
  );
};

export default FarmDepositCard;