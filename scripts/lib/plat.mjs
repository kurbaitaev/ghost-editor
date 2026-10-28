// Cross-platform helpers (macOS, Linux, Windows) for the Node scripts.
//
// - npxSync(args, opts): run `npx <args>`. On Windows npx is a .cmd shim that Node refuses to spawn without a shell.
// - venvPython(venv):    the interpreter inside a venv (bin/python or Scripts/python.exe).
// - PY:                  how to call Python on this machine, for the commands shown to the user.
import { execFileSync, spawnSync } from "node:child_process";
import os from "node:os";
import path from "node:path";

export const WIN = process.platform === "win32";
export const PY = WIN ? "python" : "python3";

export function venvPython(venv) {
  return WIN ? path.join(venv, "Scripts", "python.exe") : path.join(venv, "bin", "python");
}

export function venvDefault(envVar, name) {
  return process.env[envVar] || path.join(os.homedir(), ".venvs", name);
}

const q = (s) => (/[\s"]/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s);

export function npxSync(args, opts = {}) {
  if (WIN) return execFileSync("npx.cmd", args.map(q), { ...opts, shell: true });
  return execFileSync("npx", args, opts);
}

export function pySpawnSync(args, opts = {}) {
  return spawnSync(PY, args, opts);
}
