//handle setupevents as quickly as possible
const setupEvents = require("./setupEvents");
if (setupEvents.handleSquirrelEvent()) {
  // squirrel event handled and app will exit in 1000ms, so don't do anything else
  return;
}

const electron = require("electron");
const app = electron.app;
const BrowserWindow = electron.BrowserWindow;
const path = require("path");
const WebSocket = require("ws");
const ipcMain = require("electron").ipcMain;
const config = require("./config");
const dev_config = require("./dev_config");
const local_test = config.local_test;
const redux_tool = dev_config.redux_tool;
var url = require("url");
const Tail = require("tail").Tail;
const os = require("os");
const ChiaRunner = require("./run_chia");
// Only takes effect if local_test is false. Connects to a local introducer.

global.sharedObj = { local_test: local_test };

let chia_root = null;

async function startDaemon() {
  chia_root = await ChiaRunner.get_chia_root();
  global.sharedObj["chia_root"] = chia_root;
  await ChiaRunner.run_daemon();
  console.log("Chia root: " + chia_root);
}

app.on("ready", startDaemon);
app.on("will-quit", ChiaRunner.exit_all);

/*************************************************************
 * window management
 *************************************************************/

let mainWindow = null;

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 1200,
    minWidth: 600,
    minHeight: 800,
    backgroundColor: "#ffffff",
    show: false,
    webPreferences: {
      preload: __dirname + "/preload.js",
      nodeIntegration: true
    }
  });

  if (dev_config.redux_tool) {
    BrowserWindow.addDevToolsExtension(
      path.join(os.homedir(), dev_config.redux_tool)
    );
  }

  if (dev_config.react_tool) {
    BrowserWindow.addDevToolsExtension(
      path.join(os.homedir(), dev_config.react_tool)
    );
  }

  var startUrl =
    process.env.ELECTRON_START_URL ||
    url.format({
      pathname: path.join(__dirname, "/../build/index.html"),
      protocol: "file:",
      slashes: true
    });

  mainWindow.loadURL(startUrl);

  mainWindow.once("ready-to-show", function() {
    mainWindow.show();
  });

  // Uncomment this to open devtools by default
  // if (!guessPackaged()) {
  //   mainWindow.webContents.openDevTools();
  // }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
};

app.on("ready", createWindow);

app.on("window-all-closed", () => {
  app.quit();
});

app.on("activate", () => {
  if (mainWindow === null) {
    createWindow();
  }
});

ipcMain.on("load-page", (event, arg) => {
  mainWindow.loadURL(
    require("url").format({
      pathname: path.join(__dirname, arg.file),
      protocol: "file:",
      slashes: true
    }) + arg.query
  );
});
