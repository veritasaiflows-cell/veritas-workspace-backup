import json
import pathlib
import subprocess
import sys

cfg = json.loads(pathlib.Path(r"C:\Users\Veritas.RQs_Business\.openclaw\openclaw.json").read_text(encoding="utf-8"))
token = cfg["gateway"]["auth"]["token"]
openclaw = [
    "node",
    r"C:\Users\Veritas.RQs_Business\AppData\Roaming\npm\node_modules\openclaw\openclaw.mjs",
]

jobs = [
    [
        *openclaw,
        "cron", "add",
        "--token", token,
        "--name", "healthcheck:security-audit",
        "--description", "Weekly OpenClaw security audit for this session",
        "--cron", "0 9 * * 5",
        "--tz", "America/Phoenix",
        "--session", "current",
        "--message", "This is the scheduled weekly OpenClaw security audit reminder. Run a read-only audit using `openclaw security audit --deep` and `openclaw status --deep`, then post a concise summary here with only meaningful findings, risk changes, update availability, and next actions. Mention that this is a scheduled weekly audit reminder. Do not edit files or settings unless explicitly asked.",
        "--light-context",
        "--announce",
        "--tools", "exec",
        "--timeout-seconds", "300",
        "--json",
    ],
    [
        *openclaw,
        "cron", "add",
        "--token", token,
        "--name", "healthcheck:update-status",
        "--description", "Weekly OpenClaw update check for this session",
        "--cron", "10 9 * * 5",
        "--tz", "America/Phoenix",
        "--session", "current",
        "--message", "This is the scheduled weekly OpenClaw update reminder. Run `openclaw update status` and post a concise result here, including whether an update is available and whether action is needed. Mention that this is a scheduled weekly update reminder. Do not change anything unless explicitly asked.",
        "--light-context",
        "--announce",
        "--tools", "exec",
        "--timeout-seconds", "180",
        "--json",
    ],
]

for cmd in jobs:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    print(f"CMD: {cmd[6]}")
    if proc.stdout:
        print(proc.stdout.strip())
    if proc.stderr:
        print(proc.stderr.strip())
    print(f"EXIT: {proc.returncode}")
    if proc.returncode != 0:
        sys.exit(proc.returncode)
