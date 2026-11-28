"""What Nyarch Customize for KDE changes, without any window code.

KDE versions of Nyarch Customize's four pages:
  layouts  - Plasma panel layouts (Plasma's own scripting), backed up first
  effects  - KWin effects: blur, wobbly windows, magic lamp, desktop cube
  colours  - KDE Material You Colors: on/off and Nyarch's accent presets
  desktop  - desktop icons on (Folder View) or off (plain Desktop)

Every outside call goes through a Runner, so tests can swap in a fake one.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class Runner:
    """Runs commands. Returns (exit code, output). Never raises for a failed command."""

    def run(self, args: list[str], timeout: int = 30) -> tuple[int, str]:
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            return 127, str(e)
        return p.returncode, (p.stdout + p.stderr).strip()

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def spawn(self, args: list[str]) -> None:
        """Start a program in the background and don't wait for it."""
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass


def in_plasma() -> bool:
    """True only inside a KDE Plasma session. Panel, effect and desktop changes refuse to run
    anywhere else, so using the app from another desktop (Hyprland, say) can't start Plasma there."""
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper().split(":")


NOT_PLASMA = "This only works in a KDE Plasma session; nothing was changed."


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", str(home() / ".config")))


def data_dir() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", str(home() / ".local" / "share"))) / "nyarch-customize-kde"


# --------------------------------------------------------------------------- layouts

APPLETS_RC = "plasma-org.kde.plasma.desktop-appletsrc"
SHELL_RC = "plasmashellrc"

# Each layout is a Plasma script. It removes the current panels and builds new ones.
# Widget ids are Plasma's own (kickoff = the application launcher).
_COMMON = """
function bar(location, widgets) {
    var p = new Panel("org.kde.panel");
    p.location = location;
    p.height = 44;
    for (var i = 0; i < widgets.length; i++) { p.addWidget(widgets[i]); }
    return p;
}
function dock(location) {
    var d = new Panel("org.kde.panel");
    d.location = location;
    d.height = 56;
    d.alignment = "center";
    try { d.lengthMode = "fit"; } catch (e) {}
    try { d.floating = true; } catch (e) {}
    d.hiding = "dodgewindows";
    d.addWidget("org.kde.plasma.icontasks");
    return d;
}
var old = panels();
for (var i = 0; i < old.length; i++) { old[i].remove(); }
"""

TRAY = '"org.kde.plasma.systemtray", "org.kde.plasma.digitalclock"'

@dataclass(frozen=True)
class Layout:
    id: str
    label: str
    description: str
    script: str


LAYOUTS: list[Layout] = [
    Layout("bottom-panel", "Bottom panel",
           "One panel at the bottom: menu, open windows, tray and clock (Plasma's usual layout).",
           _COMMON + f'bar("bottom", ["org.kde.plasma.kickoff", "org.kde.plasma.icontasks", '
                     f'"org.kde.plasma.marginsseparator", {TRAY}, "org.kde.plasma.showdesktop"]);'),
    Layout("top-menu", "Top panel with menu",
           "A top bar with the menu on the left and the tray and clock on the right.",
           _COMMON + f'bar("top", ["org.kde.plasma.kickoff", "org.kde.plasma.icontasks", '
                     f'"org.kde.plasma.panelspacer", {TRAY}]);'),
    Layout("top-menu-dock", "Top panel with menu and dock",
           "A top bar with the menu, plus a floating dock of app icons at the bottom.",
           _COMMON + f'bar("top", ["org.kde.plasma.kickoff", "org.kde.plasma.panelspacer", {TRAY}]);\n'
                     'dock("bottom");'),
    Layout("top-dock", "Top panel with dock",
           "A slim top bar with the tray and clock, plus a floating dock at the bottom.",
           _COMMON + f'bar("top", ["org.kde.plasma.panelspacer", {TRAY}]);\ndock("bottom");'),
    Layout("top-left-dock", "Top panel with left dock",
           "A top bar with the menu, plus a dock of app icons on the left edge.",
           _COMMON + f'bar("top", ["org.kde.plasma.kickoff", "org.kde.plasma.panelspacer", {TRAY}]);\n'
                     'dock("left");'),
]


def backups_dir() -> Path:
    return data_dir() / "backups"


def backup_layout() -> Path | None:
    """Copy the panel and desktop settings aside. Returns the backup folder, or None if nothing to save."""
    src = config_dir()
    files = [f for f in (APPLETS_RC, SHELL_RC) if (src / f).exists()]
    if not files:
        return None
    dest = backups_dir() / time.strftime("%Y-%m-%d_%H-%M-%S")
    n = 1
    while dest.exists():
        dest = dest.with_name(dest.name.split("+")[0] + f"+{n}")
        n += 1
    dest.mkdir(parents=True)
    for f in files:
        shutil.copy2(src / f, dest / f)
    return dest


def list_backups() -> list[Path]:
    d = backups_dir()
    return sorted((p for p in d.iterdir() if p.is_dir()), reverse=True) if d.exists() else []


def _stop_plasmashell(r: Runner) -> None:
    # Plasma writes its layout when it exits, so files are only edited while it's stopped.
    code, _ = r.run(["systemctl", "--user", "stop", "plasma-plasmashell.service"])
    if code != 0:
        r.run(["kquitapp6", "plasmashell"])


def _start_plasmashell(r: Runner) -> None:
    code, _ = r.run(["systemctl", "--user", "start", "plasma-plasmashell.service"])
    if code != 0:
        r.spawn(["plasmashell"])


def restore_backup(r: Runner, backup: Path) -> tuple[bool, str]:
    if not in_plasma():
        return False, NOT_PLASMA
    files = [f for f in (APPLETS_RC, SHELL_RC) if (backup / f).exists()]
    if not files:
        return False, f"{backup} has no layout files."
    _stop_plasmashell(r)
    for f in files:
        shutil.copy2(backup / f, config_dir() / f)
    _start_plasmashell(r)
    return True, f"Restored the layout from {backup.name}."


def apply_layout(r: Runner, layout_id: str) -> tuple[bool, str]:
    if not in_plasma():
        return False, NOT_PLASMA
    layout = next((l for l in LAYOUTS if l.id == layout_id), None)
    if layout is None:
        return False, f"Unknown layout: {layout_id}"
    saved = backup_layout()
    code, out = r.run(["qdbus6", "org.kde.plasmashell", "/PlasmaShell",
                       "org.kde.PlasmaShell.evaluateScript", layout.script])
    if code != 0:
        return False, f"Plasma refused the layout: {out or 'no reply'}"
    note = f" Your previous layout is saved as {saved.name}." if saved else ""
    return True, f"Applied “{layout.label}”.{note}"


# --------------------------------------------------------------------------- effects

@dataclass(frozen=True)
class Effect:
    id: str
    label: str
    description: str
    default: bool            # KWin's own default when kwinrc says nothing
    excludes: tuple[str, ...] = ()


EFFECTS: list[Effect] = [
    Effect("blur", "Blur", "Blurs what's behind see-through panels and menus.", True),
    Effect("wobblywindows", "Wobbly windows", "Windows wobble like jelly while you drag them.", False),
    Effect("magiclamp", "Magic lamp", "Minimised windows are sucked into the panel like a genie.", False,
           excludes=("squash",)),
    Effect("cube", "Desktop cube", "Switch virtual desktops on a rotating cube (Meta+C).", False),
]


def _kread(r: Runner, file: str, group: str, key: str) -> str | None:
    code, out = r.run(["kreadconfig6", "--file", file, "--group", group, "--key", key])
    return out if code == 0 and out != "" else None


def effect_enabled(r: Runner, eff: Effect) -> bool:
    v = _kread(r, "kwinrc", "Plugins", f"{eff.id}Enabled")
    return eff.default if v is None else v.lower() == "true"


def effects_available(r: Runner) -> set[str] | None:
    """Effects KWin knows about, or None if KWin can't be asked (then assume all are there)."""
    code, out = r.run(["qdbus6", "org.kde.KWin", "/Effects", "org.freedesktop.DBus.Properties.Get",
                       "org.kde.kwin.Effects", "listOfEffects"])
    if code != 0 or not out:
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def set_effect(r: Runner, eff: Effect, on: bool) -> tuple[bool, str]:
    if not in_plasma():
        return False, NOT_PLASMA
    changes = [(eff.id, on)] + ([(x, False) for x in eff.excludes] if on else [])
    for name, state in changes:
        code, out = r.run(["kwriteconfig6", "--file", "kwinrc", "--group", "Plugins",
                           "--key", f"{name}Enabled", "--type", "bool", "true" if state else "false"])
        if code != 0:
            return False, f"Couldn't save the setting: {out}"
        method = "loadEffect" if state else "unloadEffect"
        r.run(["qdbus6", "org.kde.KWin", "/Effects", f"org.kde.kwin.Effects.{method}", name])
    return True, f"{eff.label} {'on' if on else 'off'}."


# --------------------------------------------------------------------------- colours

# Nyarch Customize's accent presets: (swatch shown, colour the scheme is built from).
ACCENTS: list[tuple[str, str]] = [
    ("#643f00", "#bc9769"), ("#005142", "#dafaef"), ("#722b65", "#dcabcc"), ("#00497e", "#d1e1f8"),
    ("#225104", "#7d916e"), ("#004397", "#4285f4"), ("#7c2c1b", "#b18c84"), ("#00504e", "#7ca7a5"),
    ("#403c8e", "#b7b4cf"), ("#3d4c00", "#b0b78e"), ("#64307c", "#8e7596"), ("#005137", "#9bb8a8"),
    ("#4e4800", "#f0eab7"),
]

MY_BIN = "kde-material-you-colors"


def my_config() -> Path:
    return config_dir() / "kde-material-you-colors" / "config.conf"


def my_autostart() -> Path:
    return config_dir() / "autostart" / "kde-material-you-colors.desktop"


def material_you_installed(r: Runner) -> bool:
    return r.which(MY_BIN) is not None


def material_you_on() -> bool:
    return my_autostart().exists()


_COLOR_LINE = re.compile(r"^\s*#?\s*color\s*=.*$")


def current_accent() -> str | None:
    """The fixed colour in Material You's settings, or None when it follows the wallpaper."""
    f = my_config()
    if not f.exists():
        return None
    for line in f.read_text().splitlines():
        m = re.match(r"^\s*color\s*=\s*(\S+)", line)
        if m:
            return m.group(1).lower()
    return None


def set_accent(r: Runner, colour: str | None) -> tuple[bool, str]:
    """colour = '#rrggbb' for a fixed accent, None to follow the wallpaper again."""
    if colour is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", colour):
        return False, f"Not a colour: {colour}"
    f = my_config()
    if not f.exists():
        if not material_you_installed(r):
            return False, "KDE Material You Colors isn't installed."
        r.run([MY_BIN, "-c"])          # writes its sample settings file
    if not f.exists():
        return False, f"Couldn't create {f}."
    lines = f.read_text().splitlines()
    new = f"color = {colour.lower()}" if colour else "#color = 255,0,1"
    out, done = [], False
    for line in lines:
        if _COLOR_LINE.match(line) and not done:
            out.append(new)
            done = True
        elif _COLOR_LINE.match(line):
            continue                   # drop duplicates
        else:
            out.append(line)
    if not done:
        idx = next((i + 1 for i, l in enumerate(out) if l.strip() == "[CUSTOM]"), len(out))
        out.insert(idx, new)
    f.write_text("\n".join(out) + "\n")
    return True, "Colours follow the wallpaper." if colour is None else f"Accent colour set to {colour}."


def set_material_you(r: Runner, on: bool) -> tuple[bool, str]:
    if not material_you_installed(r):
        return False, "KDE Material You Colors isn't installed: paru -S kde-material-you-colors"
    if on:
        if not my_config().exists():
            r.run([MY_BIN, "-c"])
        r.run([MY_BIN, "-a"])          # its own autostart entry
        r.spawn([MY_BIN])
        return True, "Wallpaper colours on. They start with Plasma from now on."
    r.run([MY_BIN, "--stop"])
    try:
        my_autostart().unlink()
    except FileNotFoundError:
        pass
    r.run(["plasma-apply-colorscheme", "BreezeDark"])
    return True, "Wallpaper colours off; back to Breeze Dark."


# --------------------------------------------------------------------------- desktop icons

FOLDER = "org.kde.plasma.folder"
PLAIN = "org.kde.desktopcontainment"   # Plasma's plain desktop, no icons
BROKEN = "org.kde.desktop"           # a wrong id 0.1.0-2 wrote; treated as "off" so the app can repair it


def _containment_plugins() -> dict[str, str]:
    """{containment id: plugin} for every top-level containment in Plasma's layout file.
    Read directly: nested groups like [Containments][1] need two --group options in
    kreadconfig6, and reading the file avoids getting that wrong."""
    f = config_dir() / APPLETS_RC
    if not f.exists():
        return {}
    out, current = {}, None
    for line in f.read_text(errors="replace").splitlines():
        line = line.strip()
        if line.startswith("["):
            m = re.fullmatch(r"\[Containments\]\[(\d+)\]", line)
            current = m.group(1) if m else None
        elif current and line.startswith("plugin="):
            out[current] = line.split("=", 1)[1].strip()
    return out


def _desktop_containments(r: Runner) -> list[str]:
    """Ids of the desktop (not panel) containments."""
    return [cid for cid, plugin in _containment_plugins().items() if plugin in (FOLDER, PLAIN, BROKEN)]


def desktop_icons_on(r: Runner) -> bool | None:
    plugins = _containment_plugins()
    ids = [c for c, p in plugins.items() if p in (FOLDER, PLAIN, BROKEN)]
    if not ids:
        return None
    return any(plugins[c] == FOLDER for c in ids)


def set_desktop_icons(r: Runner, on: bool) -> tuple[bool, str]:
    if not in_plasma():
        return False, NOT_PLASMA
    ids = _desktop_containments(r)
    if not ids:
        return False, "Couldn't find the desktop in Plasma's settings."
    saved = backup_layout()
    _stop_plasmashell(r)
    for cid in ids:
        r.run(["kwriteconfig6", "--file", APPLETS_RC, "--group", "Containments", "--group", cid,
               "--key", "plugin", FOLDER if on else PLAIN])
    _start_plasmashell(r)
    note = f" Previous layout saved as {saved.name}." if saved else ""
    return True, ("Desktop icons on." if on else "Desktop icons off.") + note
