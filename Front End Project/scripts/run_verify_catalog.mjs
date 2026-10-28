/**
 * Run scripts/verify_catalog.py with whichever Python 3 is installed.
 *
 * `python3` is the usual name on Linux and macOS but does not exist on a
 * standard Windows install, where the launcher is `py` and the executable is
 * `python`. Hard-coding either name makes the check fail on the other platform,
 * so this wrapper probes for a working Python 3 first and then runs the real
 * script with it.
 *
 * Override the interpreter with the BWE_PYTHON environment variable, e.g.
 *   PowerShell:  $env:BWE_PYTHON = "C:\Python312\python.exe"
 *   bash:        BWE_PYTHON=python3.12 npm run verify:catalog
 */
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const scriptPath = fileURLToPath(new URL("./verify_catalog.py", import.meta.url));

const isWindows = process.platform === "win32";

/** Signals a real Python 3, and rejects the Windows Store stub and Python 2. */
const PROBE = "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)";

/** Interpreters to try, most likely first for the current platform. */
const CANDIDATES = isWindows
  ? [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
      { command: "python3", args: [] },
    ]
  : [
      { command: "python3", args: [] },
      { command: "python", args: [] },
      { command: "py", args: ["-3"] },
    ];

function label(candidate) {
  return [candidate.command, ...candidate.args].join(" ");
}

function probe(candidate) {
  const result = spawnSync(candidate.command, [...candidate.args, "-c", PROBE], {
    stdio: "ignore",
  });
  return !result.error && result.status === 0;
}

function chosen() {
  const override = (process.env.BWE_PYTHON || "").trim();
  if (!override) return null;
  const [command, ...args] = override.split(/\s+/);
  return { command, args };
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

const override = chosen();
if (override) {
  if (!probe(override)) {
    fail(
      `BWE_PYTHON is set to "${label(override)}" but that is not a working ` +
        "Python 3 interpreter.\nUnset BWE_PYTHON to let the check find Python " +
        "automatically, or point it at a real python executable.",
    );
  }
  run(override);
} else {
  const candidate = CANDIDATES.find(probe);
  if (!candidate) {
    fail(
      "No Python 3 interpreter was found. The catalogue check compares the " +
        "working catalog with the original archive and needs Python 3.\n" +
        `Tried: ${CANDIDATES.map(label).join(", ")}\n` +
        "Install Python 3 from https://www.python.org/downloads/ (tick " +
        '"Add python.exe to PATH"), then run "npm run verify:catalog" again.\n' +
        "If Python is installed under a different name or path, set BWE_PYTHON.",
    );
  }
  run(candidate);
}

function run(candidate) {
  const result = spawnSync(candidate.command, [...candidate.args, scriptPath], {
    stdio: "inherit",
  });
  if (result.error) {
    fail(`Failed to start ${label(candidate)}: ${result.error.message}`);
  }
  if (result.signal) {
    fail(`The catalogue check was terminated by ${result.signal}.`);
  }
  process.exit(result.status ?? 1);
}
