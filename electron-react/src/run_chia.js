const electron = require("electron");
const app = electron.app;
const path = require("path");

const PY_MAC_DIST_FOLDER = "../../app.asar.unpacked/chia";
const PY_WIN_DIST_FOLDER = "../../app.asar.unpacked/chia";
const PY_DIST_FILE = "chia";
const PY_FOLDER = "../src/cmds";
const PY_MODULE = "chia"; // without .py suffix

var path_proc = null;
var daemon_proc = null;
var chia_root = null;

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

const guessPackaged = () => {
  if (process.platform === "win32") {
    const fullPath = path.join(__dirname, PY_WIN_DIST_FOLDER);
    packed = require("fs").existsSync(fullPath);
    console.log("guess path: " + fullPath);
    console.log(packed);
    return packed;
  }
  console.log("Not windows");
  const fullPath = path.join(__dirname, PY_MAC_DIST_FOLDER);
  packed = require("fs").existsSync(fullPath);
  console.log("guess path: " + fullPath);
  console.log(packed);
  return packed;
};

const getScriptPath = () => {
  if (!guessPackaged()) {
    return path.join(PY_FOLDER, PY_MODULE + ".py");
  }
  if (process.platform === "win32") {
    return path.join(__dirname, PY_WIN_DIST_FOLDER, PY_DIST_FILE + ".exe");
  }
  return path.join(__dirname, PY_MAC_DIST_FOLDER, PY_DIST_FILE);
};

const runDaemon = async () => {
  console.log("Run daemon");

  let script = getScriptPath();
  if (guessPackaged()) {
    try {
      console.log("Running python executable: ");
      const Process = require("child_process").spawn;
      daemon_proc = new Process(script, ["run_daemon"], processOptions);
    } catch {
      console.log("Running python executable: Error: ");
      console.log("Script " + script);
    }
  } else {
    console.log("Running python script: " + script);
    const Process = require("child_process").spawn;
    daemon_proc = new Process("python", [script, "run_daemon"], processOptions);
  }

  if (daemon_proc != null) {
    daemon_proc.stdout.setEncoding("utf8");

    daemon_proc.stdout.on("data", function(data) {
      process.stdout.write(chia_root);
    });

    daemon_proc.stderr.setEncoding("utf8");
    daemon_proc.stderr.on("data", function(data) {
      process.stdout.write("stderr: " + data.toString());
    });

    daemon_proc.on("close", function(code) {
      console.log("Daemon closing code: " + code);
    });
  }
};

async function getRootPath() {
  console.log("get root path");
  let script = getScriptPath();
  processOptions = {};
  if (guessPackaged()) {
    try {
      console.log("Running python executable: " + script);
      const Process = require("child_process").spawn;
      path_proc = new Process(script, ["version", "-r"], processOptions);
    } catch {
      console.log("Error trying to run python executable: " + script);
    }
  } else {
    console.log("Running python script: " + script);
    const Process = require("child_process").spawn;
    path_proc = new Process(
      "python",
      [script, "version", "-r"],
      processOptions
    );
  }

  if (path_proc != null) {
    path_proc.stdout.setEncoding("utf8");

    path_proc.stdout.on("data", function(data) {
      chia_root = data.toString();
      process.stdout.write(chia_root);
    });

    path_proc.stderr.setEncoding("utf8");
    path_proc.stderr.on("data", function(data) {
      process.stdout.write("stderr: " + data.toString());
    });

    path_proc.on("close", function(code) {
      console.log("closing code: " + code);
    });
  }

  while (chia_root == null) {
    await sleep(100);
  }

  return chia_root;
}

const exitProcs = () => {
  // Should be a setting
  if (path_proc != null) {
    if (process.platform === "win32") {
      process.stdout.write("Killing path proccess on windows");
      var cp = require("child_process");
      cp.execSync("taskkill /PID " + path_proc.pid + " /T /F");
    } else {
      process.stdout.write("Killing daemon on other platforms");
      path_proc.kill();
      path_proc = null;
      path_proc = null;
    }
  }
  if (daemon_proc != null) {
    if (process.platform === "win32") {
      process.stdout.write("Killing daemon proccess on windows");
      var cp = require("child_process");
      cp.execSync("taskkill /PID " + daemon_proc.pid + " /T /F");
    } else {
      process.stdout.write("Killing daemon on other platforms");
      daemon_proc.kill();
      daemon_proc = null;
      daemon_proc = null;
    }
  }
};

module.exports = {
  run_daemon: runDaemon,
  get_chia_root: getRootPath,
  exit_all: exitProcs
};
