import React from "react"
import { Grid } from "@material-ui/core";
import { makeStyles } from "@material-ui/core/styles";
import WarningIcon from '@material-ui/icons/Warning';

const useStyles = makeStyles((theme) => ({
  warningIcon: {
    color: theme.palette.warning.main,
  },
  warningMessage: {
    marginLeft: "4px",
    fontSize: 12,
  },
  warningBorder: {
    border: "1px solid",
    borderColor: theme.palette.warning.main,
    borderRadius: "4px",
    padding: "4px",
  }
}));

export default function FarmEmergencyWarning() {
  const classes = useStyles();

  return (
    <>
      <Grid className={classes.warningBorder} container direction="row" alignItems="center">
        <Grid item>
          <WarningIcon className={classes.warningIcon} fontSize="small"/>
        </Grid>
        <Grid className={classes.warningMessage} item>
          All funds were temporarily withdrawn due to emergency.
        </Grid>
      </Grid>
    </>
  );
}