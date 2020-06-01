import React from "react";
import {
  makeStyles,
  Typography,
  Button,
  Box,
  TextField,
  Backdrop,
  CircularProgress
} from "@material-ui/core";

import {
  createState,
  changeCreateWallet,
  CREATE_AP_WALLET_OPTIONS
} from "../modules/createWalletReducer";
import { useDispatch, useSelector } from "react-redux";
import ArrowBackIosIcon from "@material-ui/icons/ArrowBackIos";
import { useStyles } from "./CreateWallet";