import React from "react";
import {
  makeStyles,
  Typography,
  Button,
  Paper,
  Box,
  TextField,
  Backdrop,
  CircularProgress
} from "@material-ui/core";

import {
  changeCreateWallet,
  CREATE_AP_WALLET_OPTIONS
} from "../modules/createWalletReducer";
import { useDispatch, useSelector } from "react-redux";
import ArrowBackIosIcon from "@material-ui/icons/ArrowBackIos";
import { useStyles } from "./CreateWallet";
import { get_unused_pubkey } from "../modules/message";
import Grid from "@material-ui/core/Grid";

export const customStyles = makeStyles(theme => ({
  input: {
    marginLeft: theme.spacing(3),
    marginRight: theme.spacing(3),
    height: 56
  },
  generate: {
    paddingLeft: "0px",
    marginLeft: theme.spacing(3),
    marginRight: theme.spacing(3),

    height: 56,
    width: 150
  },
  card: {
    paddingTop: theme.spacing(10),
    height: 200
  },
  pubkeyContainer: {
    marginLeft: theme.spacing(3)
  },
  copyButton: {
    marginTop: theme.spacing(0),
    marginBottom: theme.spacing(0),
    width: 50,
    height: 56
  }
}));

export const CreateAuthorizerAPWallet = () => {
  const classes = useStyles();
  const custom = customStyles();
  const dispatch = useDispatch();
  const id = useSelector(state => state.wallet_state.wallets[1].id);
  const ap_pubkey = useSelector(
    state => state.wallet_state.wallets[1].ap_pubkey
  );
  var open = false;
  var pending = useSelector(state => state.create_options.pending);
  var created = useSelector(state => state.create_options.created);

  function goBack() {
    dispatch(changeCreateWallet(CREATE_AP_WALLET_OPTIONS));
  }

  function newPubkey() {
    dispatch(get_unused_pubkey(id));
  }

  function copy() {
    navigator.clipboard.writeText(ap_pubkey);
  }

  return (
    <div>
      <div className={classes.cardTitle}>
        <Box display="flex">
          <Box>
            <Button onClick={goBack}>
              <ArrowBackIosIcon> </ArrowBackIosIcon>
            </Button>
          </Box>
          <Box flexGrow={1} className={classes.title}>
            <Typography component="h6" variant="h6">
              Generate Authorizer Pubkey
            </Typography>
          </Box>
        </Box>
      </div>
      <div className={custom.card}>
        <Box display="flex">
          <Box flexGrow={1}>
            <TextField
              className={custom.pubkeyContainer}
              disabled
              fullWidth
              label="Generate an AP Authorizer Pubkey to send to your AP Spender..."
              value={ap_pubkey}
              variant="outlined"
            />
          </Box>
          <Box>
            <Button
              onClick={copy}
              className={custom.copyButton}
              variant="contained"
              color="secondary"
              disableElevation
            >
              Copy
            </Button>
          </Box>
          <Box>
            <Button
              onClick={newPubkey}
              className={custom.generate}
              variant="contained"
              color="primary"
            >
              Generate AP pubkey
            </Button>
            <Backdrop className={custom.backdrop} open={open} invisible={false}>
              <CircularProgress color="inherit" />
            </Backdrop>
          </Box>
        </Box>
      </div>
      <Backdrop className={classes.backdrop} open={pending && created}>
        <CircularProgress color="inherit" />
      </Backdrop>
  </div>

  );
};