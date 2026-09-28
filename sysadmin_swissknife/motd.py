"""MOTD builder: ASCII-art banners, frames, colors, static /etc/motd or dynamic login scripts.

No GUI code here: ``build()`` returns the preview lines and the file content, so everything
is unit tested (the generated bash scripts are checked with ``bash -n`` and executed).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pyfiglet

from . import __version__

# ----------------------------------------------------------------------------- options
FONTS = ["standard", "slant", "small", "small_slant", "big", "doom", "banner3", "ansi_shadow",
         "ansi_regular", "block", "shadow", "larry3d", "ogre", "speed", "lean", "colossal",
         "electronic", "calvin_s", "digital", "isometric1"]

COLORS = {            # name -> ANSI SGR code (None = no color)
    "none": None, "white": "1;37", "red": "1;31", "green": "1;32", "yellow": "1;33",
    "blue": "1;34", "magenta": "1;35", "cyan": "1;36", "gray": "0;37",
}
PREVIEW_COLORS = {    # name -> color used by the GUI preview
    None: "#d0d0d0", "white": "#ffffff", "red": "#ff5f5f", "green": "#5fd75f",
    "yellow": "#ffd75f", "blue": "#5f87ff", "magenta": "#d75fd7", "cyan": "#5fd7ff",
    "gray": "#a8a8a8", "none": "#d0d0d0",
}

FRAMES = {            # name -> (top-left, horizontal, top-right, vertical, bottom-left, bottom-right)
    "none": None,
    "single": ("\u250c", "\u2500", "\u2510", "\u2502", "\u2514", "\u2518"),
    "rounded": ("\u256d", "\u2500", "\u256e", "\u2502", "\u2570", "\u256f"),
    "double": ("\u2554", "\u2550", "\u2557", "\u2551", "\u255a", "\u255d"),
    "ascii": ("+", "-", "+", "|", "+", "+"),
    "hash": ("#", "#", "#", "#", "#", "#"),
}

ICONS = {
    "none": [],
    "server": [
        " .----------. ",
        " | ==    o  | ",
        " |----------| ",
        " | ==    o  | ",
        " |----------| ",
        " | ==    o  | ",
        " '----------' ",
    ],
    "cloud": [
        "       .--.      ",
        "    .-(    ).    ",
        "   (___.__)__)   ",
    ],
    "terminal": [
        " .--------------. ",
        " | >_           | ",
        " |              | ",
        " '--------------' ",
    ],
}

# key -> (label, bash command printing the value, sample value for the preview)
INFO_FIELDS = {
    "hostname": ("Hostname", "hostname -f 2>/dev/null || hostname", "web01.example.com"),
    "os": ("OS", '. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-$(uname -s)}"',
           "Oracle Linux Server 8.9"),
    "kernel": ("Kernel", "uname -r", "5.15.0-205.149.5.el8uek.x86_64"),
    "ip": ("IP address", "hostname -I 2>/dev/null | awk '{print $1}'", "192.168.1.10"),
    "uptime": ("Uptime", "uptime -p 2>/dev/null | sed 's/^up //'", "12 days, 3 hours"),
    "load": ("Load", "cut -d' ' -f1-3 /proc/loadavg", "0.12 0.08 0.05"),
    "cpu": ("CPU", 'echo "$(nproc) cores"', "8 cores"),
    "memory": ("Memory", "free -h | awk '/^Mem:/{print $3\" used / \"$2}'", "3.1Gi used / 15Gi"),
    "disk": ("Disk /", "df -h / | awk 'NR==2{print $3\" used / \"$2\" (\"$5\")\"}'",
             "18G used / 50G (36%)"),
    "users": ("Users", 'echo "$(who | wc -l) logged in"', "2 logged in"),
    "date": ("Date", "date '+%Y-%m-%d %H:%M %Z'", "2026-09-28 09:30 CEST"),
}

TARGETS = {
    "static": ("Static text for /etc/motd", "motd"),
    "debian": ("Dynamic script - Ubuntu/Debian (/etc/update-motd.d)", "99-swissknife-motd"),
    "rhel": ("Dynamic script - RHEL/Oracle Linux/Rocky/CentOS (/etc/profile.d)",
             "swissknife-motd.sh"),
}

LEGAL_EN = ("WARNING: Authorized access only.\n"
            "All activities on this system are logged and monitored.\n"
            "Disconnect immediately if you are not an authorized user.")
LEGAL_IT = ("ATTENZIONE: accesso consentito solo al personale autorizzato.\n"
            "Tutte le attivita' su questo sistema sono registrate e monitorate.\n"
            "Se non sei autorizzato, disconnettiti immediatamente.")


@dataclass
class MotdConfig:
    banner: str = "web01"
    font: str = "standard"
    banner_color: str = "cyan"
    icon: str = "none"
    frame: str = "none"
    center: bool = False
    message: str = ""
    message_color: str = "yellow"
    info: list[str] = field(default_factory=lambda: ["hostname", "os", "kernel", "ip", "uptime"])
    info_color: str = "green"
    target: str = "static"
    width: int = 100          # max banner width passed to figlet


@dataclass
class MotdResult:
    preview: list[list[tuple[str, str | None]]]   # lines of (text, color name)
    content: str                                  # file to install
    filename: str
    install: str                                  # how to install it
    warnings: list[str]


# ----------------------------------------------------------------------------- helpers
def banner_lines(text: str, font: str, width: int = 100) -> list[str]:
    if not text.strip():
        return []
    art = pyfiglet.figlet_format(text, font=font, width=width)
    lines = [l.rstrip() for l in art.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    while lines and not lines[0].strip():
        lines.pop(0)
    return lines


def sq(text: str) -> str:
    """Single-quote a string for bash."""
    return "'" + text.replace("'", "'\"'\"'") + "'"


def sgr(color: str | None) -> str:
    code = COLORS.get(color or "none")
    return f"\x1b[{code}m" if code else ""


# Content items: ("text", str, color) or ("info", key, color)
def _items(cfg: MotdConfig, dynamic: bool):
    items = []
    for line in ICONS.get(cfg.icon, []):
        items.append(("text", line, cfg.banner_color))
    if ICONS.get(cfg.icon):
        items.append(("text", "", None))
    for line in banner_lines(cfg.banner, cfg.font, cfg.width):
        items.append(("text", line, cfg.banner_color))
    msg = [l.rstrip() for l in cfg.message.strip("\n").split("\n")] if cfg.message.strip() else []
    if msg:
        items.append(("text", "", None))
        items += [("text", l, cfg.message_color) for l in msg]
    if dynamic and cfg.info:
        items.append(("text", "", None))
        items += [("info", k, cfg.info_color) for k in cfg.info if k in INFO_FIELDS]
    return items


LABEL_W = 12


def build(cfg: MotdConfig) -> MotdResult:
    dynamic = cfg.target in ("debian", "rhel")
    warnings = []
    if cfg.font not in pyfiglet.FigletFont.getFonts():
        warnings.append(f"font {cfg.font!r} not available, using 'standard'")
        cfg.font = "standard"
    if not dynamic and cfg.info:
        warnings.append("system information needs a dynamic script: "
                        "choose Ubuntu/Debian or RHEL as output to include it")
    items = _items(cfg, dynamic)

    text_w = max([len(t) for kind, t, _ in items if kind == "text"] + [0])
    info_w = max([LABEL_W + 1 + len(INFO_FIELDS[k][2]) for kind, k, _ in items if kind == "info"] + [0])
    inner = max(text_w, info_w, 40 if dynamic and cfg.info else 0)
    value_w = inner - LABEL_W - 1
    fr = FRAMES.get(cfg.frame)
    pad = 1 if fr else 0

    def place(t: str) -> str:
        if cfg.center:
            left = (inner - len(t)) // 2
            return (" " * left + t).ljust(inner)
        return t.ljust(inner)

    # ---------------------------------------------------------------- preview (sample values)
    preview: list[list[tuple[str, str | None]]] = []
    fc = cfg.banner_color

    def framed(segs):
        if not fr:
            return segs
        return [(fr[3] + " " * pad, fc)] + segs + [(" " * pad + fr[3], fc)]

    if fr:
        preview.append([(fr[0] + fr[1] * (inner + 2 * pad) + fr[2], fc)])
    for kind, val, color in items:
        if kind == "text":
            line = place(val) if (fr or cfg.center) else val
            preview.append(framed([(line, color)]))
        else:
            label, _, sample = INFO_FIELDS[val]
            v = sample[:value_w] if fr else sample
            body = f"{label + ':':<{LABEL_W}} " + (v.ljust(value_w) if fr else v)
            preview.append(framed([(body, color)]))
    if fr:
        preview.append([(fr[4] + fr[1] * (inner + 2 * pad) + fr[5], fc)])

    # ---------------------------------------------------------------- file content
    filename = TARGETS[cfg.target][1]
    if not dynamic:
        out = []
        for segs in preview:
            out.append("".join((sgr(c) + t + ("\x1b[0m" if sgr(c) else "")) if t else t
                               for t, c in segs).rstrip())
        content = "\n".join(out) + "\n"
        install = ("sudo cp motd /etc/motd\n\n"
                   "# RHEL/Oracle Linux: shown by sshd (PrintMotd yes) at login.\n"
                   "# Ubuntu: /etc/motd is shown after the update-motd.d scripts.")
        return MotdResult(preview, content, filename, install, warnings)

    sh = ["#!/bin/bash",
          f"# Login banner generated by Sysadmin Swissknife {__version__}"]
    if cfg.target == "rhel":
        sh += ["# Sourced by login shells: only run for interactive sessions",
               "case $- in *i*) ;; *) return 0 2>/dev/null || exit 0 ;; esac"]
    sh += ["", "R=$'\\e[0m'"]
    used = sorted({c for _, _, c in items if COLORS.get(c or "none")} | ({fc} if fr and COLORS.get(fc) else set()))
    var = {}
    for i, c in enumerate(used):
        var[c] = f"C{i}"
        sh.append(f"C{i}=$'\\e[{COLORS[c]}m'   # {c}")
    for c in COLORS:
        var.setdefault(c, "")
    var[None] = ""

    def cv(c):
        return f"${{{var[c]}}}" if var.get(c) else ""

    def rv(c):
        return "${R}" if var.get(c) else ""

    info_keys = [v for k, v, _ in items if k == "info"]
    if info_keys:
        sh += ["", "# system information"]
        for k in info_keys:
            sh.append(f"V_{k}=$({INFO_FIELDS[k][1]})")
    sh.append("")

    fl = cv(fc) if fr else ""
    fr_r = rv(fc) if fr else ""
    if fr:
        sh.append(f"printf '%s\\n' \"{fl}\"{sq(fr[0] + fr[1] * (inner + 2 * pad) + fr[2])}\"{fr_r}\"")
    for kind, val, color in items:
        if kind == "text":
            line = place(val) if (fr or cfg.center) else val
            if fr:
                sh.append(f"printf '%s\\n' \"{fl}\"{sq(fr[3] + ' ' * pad)}\"{fr_r}{cv(color)}\""
                          f"{sq(line)}\"{rv(color)}{fl}\"{sq(' ' * pad + fr[3])}\"{fr_r}\"")
            elif line:
                sh.append(f"printf '%s\\n' \"{cv(color)}\"{sq(line)}\"{rv(color)}\"")
            else:
                sh.append("echo")
        else:
            label = INFO_FIELDS[val][0] + ":"
            if fr:
                sh.append(f"printf '%s%s%s%s%-{LABEL_W}s %-{value_w}.{value_w}s%s%s%s%s\\n' "
                          f"\"{fl}\" {sq(fr[3] + ' ' * pad)} \"{fr_r}\" \"{cv(color)}\" "
                          f"{sq(label)} \"$V_{val}\" \"{rv(color)}\" \"{fl}\" "
                          f"{sq(' ' * pad + fr[3])} \"{fr_r}\"")
            else:
                sh.append(f"printf '%s%-{LABEL_W}s %s%s\\n' \"{cv(color)}\" {sq(label)} "
                          f"\"$V_{val}\" \"{rv(color)}\"")
    if fr:
        sh.append(f"printf '%s\\n' \"{fl}\"{sq(fr[4] + fr[1] * (inner + 2 * pad) + fr[5])}\"{fr_r}\"")
    sh.append("")
    content = "\n".join(sh)
    if cfg.target == "debian":
        install = (f"sudo install -m 755 {filename} /etc/update-motd.d/{filename}\n\n"
                   "# optional: hide the default Ubuntu messages\n"
                   "sudo chmod -x /etc/update-motd.d/10-help-text /etc/update-motd.d/50-motd-news\n\n"
                   f"# test it:  run-parts /etc/update-motd.d/")
    else:
        install = (f"sudo install -m 644 {filename} /etc/profile.d/{filename}\n\n"
                   "# shown at every interactive login (ssh or console)\n"
                   f"# test it:  bash -ic 'source /etc/profile.d/{filename}'")
    return MotdResult(preview, content, filename, install, warnings)
