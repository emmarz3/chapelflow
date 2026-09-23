import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { spawn } from "node:child_process";

const localPython = resolve(
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);
const python =
  process.env.CHAPELFLOW_PYTHON ||
  (existsSync(localPython) ? localPython : "python");
const cwd = resolve("chapelflow-backend");
const env = {
  ...process.env,
  DJANGO_SETTINGS_MODULE:
    process.env.DJANGO_SETTINGS_MODULE || "config.settings.local",
};
const args = process.argv.slice(2);
const child = spawn(
  python,
  ["manage.py", ...(args.length ? args : ["runserver", "127.0.0.1:8000"])],
  { cwd, env, stdio: "inherit", windowsHide: true },
);
child.on("error", (error) => {
  console.error(
    `Cannot start Django: ${error.message}. Install requirements into .venv first.`,
  );
  process.exitCode = 1;
});
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
