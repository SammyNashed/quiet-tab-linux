#!/usr/bin/env python3
"""Seeds Helium's native "Colors" accent (Preferences: browser.theme.user_color2)
from a matugen hex color, and keeps it live: if Helium is running, this
gracefully quits it, writes the new color while it's safely closed, then
relaunches it with --restore-last-session so open tabs come back.
Called from matugen's post_hook with 1 hex arg.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PREFS = Path.home() / ".config" / "net.imput.helium" / "Default" / "Preferences"
COLOR_VARIANT = 2  # "Vibrant" -- confirmed working via manual test on 2026-09-19
QUIT_TIMEOUT = 20  # seconds to wait for a graceful shutdown before giving up


def hex_to_skcolor(h):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    unsigned = (0xFF << 24) | (r << 16) | (g << 8) | b
    return unsigned - 0x100000000 if unsigned >= 0x80000000 else unsigned


def running_pids():
    out = subprocess.run(["pgrep", "-x", "helium"], capture_output=True, text=True)
    return [int(p) for p in out.stdout.split()]


def main_pid():
    """The top-level browser process has no --type= flag; zygote/renderer/GPU
    child processes share the same binary name but all carry --type=."""
    for pid in running_pids():
        try:
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
        except FileNotFoundError:
            continue
        if b"--type=" not in cmdline:
            return pid
    return None


def quit_helium():
    pid = main_pid()
    if pid is None:
        return True
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + QUIT_TIMEOUT
    while time.monotonic() < deadline:
        if not running_pids():
            return True
        time.sleep(0.3)
    return not running_pids()


def relaunch_helium():
    # Scrub Claude Code session markers so the relaunched browser doesn't
    # inherit them (see memory: claude-session-env-leak).
    env = {k: v for k, v in os.environ.items() if "CLAUDE" not in k.upper() and k != "NO_COLOR"}
    subprocess.Popen(
        ["helium-browser", "--restore-last-session"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def main():
    if len(sys.argv) != 2:
        print("usage: set_helium_accent.py <primary_hex>", file=sys.stderr)
        sys.exit(1)

    was_running = bool(running_pids())

    if was_running and not quit_helium():
        print("set_helium_accent: Helium didn't quit in time, skipping to avoid clobbering Preferences", file=sys.stderr)
        sys.exit(0)

    if not PREFS.exists():
        sys.exit(0)

    prefs = json.loads(PREFS.read_text())
    theme = prefs.setdefault("browser", {}).setdefault("theme", {})
    theme["user_color2"] = hex_to_skcolor(sys.argv[1])
    theme["color_variant2"] = COLOR_VARIANT
    theme["follows_system_colors"] = False
    PREFS.write_text(json.dumps(prefs))

    if was_running:
        relaunch_helium()


if __name__ == "__main__":
    main()
