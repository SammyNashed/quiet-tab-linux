#!/usr/bin/env python3
"""Quiet Tab's Linux helper: a native messaging host the browser starts on demand.

It tells the extension two things, and again whenever either changes:

  wallpaper  a small JPEG thumbnail of the current wallpaper (for the swatches,
             the click-to-pick preview and the Wallpaper source)
  matugen    the exact colours matugen generated from it, dark and light, read
             from the file the Quiet Tab matugen template writes

It only reads. Nothing in the browser or the desktop is changed.

Wallpaper lookup, first hit wins: awww/swww, hyprpaper, ~/.cache/current_wallpaper,
waypaper's config, GNOME/Cinnamon/MATE gsettings.

    quiet-tab-helper.py            run as a host (the browser does this)
    quiet-tab-helper.py --check    print what it would send, then exit
"""
import base64
import configparser
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time

VERSION = "2.0.0"
THUMB_MAX = 480
HOME = os.path.expanduser("~")
CACHE = os.environ.get("XDG_CACHE_HOME") or os.path.join(HOME, ".cache")
MATUGEN_FILE = os.environ.get("QUIET_TAB_COLORS") or os.path.join(CACHE, "quiet-tab", "colors.json")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff", ".jxl", ".avif")

_write_lock = threading.Lock()
_resend = threading.Event()
_resend.set()


def send(obj):
    body = json.dumps(obj).encode()
    with _write_lock:
        sys.stdout.buffer.write(struct.pack("=I", len(body)) + body)
        sys.stdout.buffer.flush()


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


# --------------------------------------------------------------- wallpaper

def _from_awww():
    for tool in ("awww", "swww"):
        if shutil.which(tool):
            for line in run([tool, "query"]).splitlines():
                if "image: " in line:
                    return line.split("image: ", 1)[1].strip()
    return None


def _from_hyprpaper():
    if shutil.which("hyprctl"):
        for line in run(["hyprctl", "hyprpaper", "listactive"]).splitlines():
            if "=" in line:
                return line.split("=", 1)[1].strip()
    return None


def _from_cache():
    p = os.path.join(CACHE, "current_wallpaper")
    return p if os.path.isfile(p) else None


def _from_waypaper():
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        cfg.read(os.path.join(HOME, ".config", "waypaper", "config.ini"))
        return os.path.expanduser(cfg["Settings"]["wallpaper"].split(",")[0].strip())
    except (KeyError, configparser.Error):
        return None


def _from_gsettings():
    if not shutil.which("gsettings"):
        return None
    for schema, key in (("org.gnome.desktop.background", "picture-uri-dark"),
                        ("org.gnome.desktop.background", "picture-uri"),
                        ("org.cinnamon.desktop.background", "picture-uri"),
                        ("org.mate.background", "picture-filename")):
        v = run(["gsettings", "get", schema, key]).strip().strip("'")
        if v:
            return v[7:] if v.startswith("file://") else v
    return None


def current_wallpaper():
    for finder in (_from_awww, _from_hyprpaper, _from_cache, _from_waypaper, _from_gsettings):
        p = finder()
        if p and os.path.isfile(p) and p.lower().endswith(IMAGE_EXTS + ("current_wallpaper",)):
            return p
    return None


def thumbnail(path):
    """JPEG data URL no larger than THUMB_MAX on its long side."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((THUMB_MAX, THUMB_MAX))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
            data = buf.getvalue()
    except Exception:
        data = None
    if data is None:
        try:
            import gi
            gi.require_version("GdkPixbuf", "2.0")
            from gi.repository import GdkPixbuf
            pb = GdkPixbuf.Pixbuf.new_from_file_at_size(path, THUMB_MAX, THUMB_MAX)
            ok, data = pb.save_to_bufferv("jpeg", ["quality"], ["85"])
            data = bytes(data) if ok else None
        except Exception:
            data = None
    if data is None:
        return None
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def signature(path):
    try:
        st = os.stat(path)
        return f"{path}:{int(st.st_mtime)}:{st.st_size}"
    except OSError:
        return None


# ----------------------------------------------------------------- matugen

def read_matugen():
    try:
        st = os.stat(MATUGEN_FILE)
        with open(MATUGEN_FILE) as f:
            data = json.load(f)
        if isinstance(data.get("dark"), dict) and isinstance(data.get("light"), dict):
            return f"matugen:{int(st.st_mtime)}:{st.st_size}", data
    except (OSError, ValueError):
        pass
    return None, None


# -------------------------------------------------------------------- loop

def reader():
    stdin = sys.stdin.buffer
    while True:
        head = stdin.read(4)
        if len(head) < 4:
            os._exit(0)   # browser closed the port
        body = stdin.read(struct.unpack("=I", head)[0])
        try:
            if json.loads(body).get("type") == "refresh":
                _resend.set()
        except ValueError:
            pass


def main():
    if "--check" in sys.argv:
        wp = current_wallpaper()
        stamp, colors = read_matugen()
        print("wallpaper:", wp or "not found")
        print("thumbnail:", "ok" if wp and thumbnail(wp) else "failed")
        print("matugen:  ", MATUGEN_FILE if colors else f"no colours at {MATUGEN_FILE}")
        if colors:
            print("  primary dark/light:", colors["dark"].get("primary"), colors["light"].get("primary"))
        return
    threading.Thread(target=reader, daemon=True).start()
    send({"type": "hello", "version": VERSION})
    last_wp = last_mg = None
    while True:
        force = _resend.is_set()
        _resend.clear()
        wp = current_wallpaper()
        sig = (signature(wp) if wp else None) or "none"
        if force or sig != last_wp:
            last_wp = sig
            msg = {"type": "wallpaper", "stamp": sig}
            if wp:
                msg["source"] = "linux"
                msg["title"] = os.path.basename(os.path.realpath(wp))
                image = thumbnail(wp)
                if image:
                    msg["image"] = image
            send(msg)
        stamp, colors = read_matugen()
        if colors and (force or stamp != last_mg):
            last_mg = stamp
            send({"type": "matugen", "stamp": stamp, "dark": colors["dark"], "light": colors["light"]})
        _resend.wait(2)


if __name__ == "__main__":
    main()
