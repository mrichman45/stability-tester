"""Checks for every fix from our Linux journey, with automatic repairs.

Each check returns a Result, or None when it doesn't apply to this computer.
A check runs when the laptop's profile in machines.json lists it, or when the thing it
checks is installed anyway (so fixes carry over between laptops).
"""

import json
import os
import re
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import fixers
from .util import (DATA_DIR, GID, HOME, SRC_DIR, UID, USER, kread, repo_dir, kwrite_cmd, pkg_required_by, pkg_version,
                   read, repo_versions, run, shell_quote, unit_state, upstream,
                   groups_configured, groups_in_session, login_shell, which)

OK, WARN, FAIL, SKIP, INFO = "ok", "warn", "fail", "skip", "info"


def _cap(s):
    return s[:1].upper() + s[1:]

WINDOWS_MOUNT = "/mnt/windows"


def windows_partition(ctx):
    """UUID of the Windows (NTFS) partition: your saved setting, else the largest NTFS partition.
    Nothing personal is stored in the repo; a found UUID is only remembered on this laptop."""
    saved = (ctx.cfg or {}).get("windows_drive_uuid")
    if saved and Path(f"/dev/disk/by-uuid/{saved}").exists():
        return saved
    rc, out, _ = run(["lsblk", "-brno", "UUID,FSTYPE,SIZE"])
    best, size = None, 0
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1] in ("ntfs", "ntfs3") and parts[2].isdigit() and int(parts[2]) > size:
            best, size = parts[0], int(parts[2])
    if best and ctx.cfg is not None:
        ctx.cfg["windows_drive_uuid"] = best
    return best


@dataclass
class Fix:
    summary: str                                   # one line, used in the guide's fix log
    script: list = field(default_factory=list)     # shell lines (may use sudo); run in a terminal
    python: Optional[Callable[[], str]] = None      # user-level file edit done by the app itself
    preview: str = ""                              # e.g. the new file contents
    after: str = ""                                # e.g. "Log out and back in"
    danger: str = ""                               # shown as an extra warning before confirming


@dataclass
class Result:
    status: str
    detail: str
    fix: Optional[Fix] = None
    manual: str = ""


@dataclass
class Check:
    id: str
    title: str
    guide: str               # anchor in GUIDE.md
    func: Callable
    preference: bool = False  # a choice you made (can be ignored without nagging)


class Context:
    def __init__(self, machine, gui=False, cfg=None):
        self.machine = machine
        self.gui = gui
        self.cfg = cfg
        self.root = {}        # filled by gather_root()

    def expects(self, check_id):
        """True when this laptop's profile (machines.json) includes the fix."""
        return check_id in self.machine.checks

    def gather_root(self, needed):
        """Read Secure Boot and drive status through the one administrator session."""
        if not needed or self.root.get("_ok"):
            return
        from .root import RootSession
        try:
            rc, lines = RootSession.get(self.gui).call("setup-info")
            self.root = json.loads("\n".join(lines))
            self.root["_ok"] = rc == 0
        except (PermissionError, RuntimeError, json.JSONDecodeError):
            self.root = {"_ok": False}


# ---------------------------------------------------------------- checks

def c_reboot(ctx):
    kernel = os.uname().release
    if not Path(f"/usr/lib/modules/{kernel}").exists():
        return Result(WARN, f"A kernel update was installed, but you're still running {kernel}.",
                      manual="Reboot to start the new kernel (and NVIDIA driver).")
    return Result(OK, f"Running the installed kernel ({kernel}).")


def c_updates(ctx):
    if not which("checkupdates"):
        return Result(WARN, "Can't check for updates (pacman-contrib isn't installed).", Fix(
            "Updated the system", ["sudo pacman -Syu --needed pacman-contrib"], after="Reboot if the kernel was updated."))
    rc, out, _ = run(["checkupdates"], timeout=180)
    if rc == 2:
        return Result(OK, "The system is up to date.")
    if rc != 0:
        return Result(WARN, "Couldn't reach the package servers to check for updates.",
                      manual="Check the internet connection, or run 'sudo cachyos-rate-mirrors'.")
    n = len([l for l in out.splitlines() if l.strip()])
    kernel = any(l.startswith(("linux", "nvidia")) for l in out.splitlines())
    return Result(WARN, f"{n} updates available" + (" (including the kernel or NVIDIA driver)." if kernel else "."),
                  Fix("Updated the system", ["sudo pacman -Syu"], after="Reboot afterwards." if kernel else ""))


def c_nvidia(ctx):
    main = pkg_version("nvidia-utils")
    if not main:
        if ctx.expects("nvidia"):
            return Result(INFO, "The NVIDIA driver isn't installed.",
                          manual="Open CachyOS Hello → Apps/Tweaks → hardware detection, or run 'sudo chwd -a'. Then reboot.")
        return None
    lib32 = pkg_version("lib32-nvidia-utils")
    avail_main = repo_versions("nvidia-utils")
    avail_32 = repo_versions("lib32-nvidia-utils")

    def matching_repo(target):
        for repo, ver in avail_32:
            if upstream(ver) == upstream(target):
                return repo
        return None

    if lib32 and upstream(lib32) != upstream(main):
        repo = matching_repo(main)
        detail = f"The driver is {upstream(main)} but its 32-bit copy is {upstream(lib32)}."
        if repo:
            return Result(FAIL, detail, Fix(
                f"Installed lib32-nvidia-utils from {repo} to match the driver",
                [f"sudo pacman -Syu {repo}/lib32-nvidia-utils"], after="Reboot afterwards."))
        return Result(FAIL, detail, manual="No repository has the matching 32-bit driver yet. Wait a few hours and update again.")

    if lib32 and avail_main and avail_32 and upstream(avail_main[0][1]) != upstream(avail_32[0][1]):
        target = avail_main[0][1]
        repo = matching_repo(target)
        detail = (f"Your next update will stop with an NVIDIA error: the new driver is {upstream(target)}, "
                  f"but the preferred repository's 32-bit copy is {upstream(avail_32[0][1])}.")
        if repo:
            return Result(WARN, detail, Fix(
                f"Updated with lib32-nvidia-utils taken from {repo}",
                [f"sudo pacman -Syu {repo}/lib32-nvidia-utils"], after="Reboot afterwards."))
        return Result(WARN, detail, manual="Wait a few hours for the 32-bit driver, then update.")

    return Result(OK, f"NVIDIA driver {upstream(main)}" + (" with a matching 32-bit copy." if lib32 else "."))


KERNEL_RE = re.compile(r"^linux(-cachyos(-[a-z0-9]+)*|-lts|-zen|-hardened|-rt(-lts)?)?$")
KERNEL_EXTRA = ("-headers", "-nvidia", "-nvidia-open", "-api-headers", "-firmware", "-docs", "-zfs")


def installed_kernels():
    rc, out, _ = run(["pacman", "-Qq"])
    return [p for p in out.split() if KERNEL_RE.match(p) and not p.endswith(KERNEL_EXTRA)] if rc == 0 else []


def running_kernel_package():
    return read(f"/usr/lib/modules/{os.uname().release}/pkgbase").strip()


def c_kernel(ctx):
    want = getattr(ctx.machine, "kernel", "")
    if not want or not ctx.expects("kernel"):
        return None
    have = installed_kernels()
    running = running_kernel_package()
    nvidia = bool(pkg_version("nvidia-utils"))
    if want not in have:
        script = [f"sudo pacman -S --needed {want} {want}-headers" + (f" {want}-nvidia-open" if nvidia else "")]
        return Result(FAIL, f"{want} isn't installed (installed: {', '.join(have) or 'none'}).",
                      Fix(f"Installed {want}", script,
                          after="Run 'sudo sbctl verify' and sign anything marked ✗, reboot into it, then run Checkup "
                                "again to remove the other kernels."))
    missing = [p for p in ([f"{want}-headers"] + ([f"{want}-nvidia-open"] if nvidia else [])) if not pkg_version(p)]
    if nvidia and pkg_version(f"{want}-nvidia"):
        missing = [m for m in missing if not m.endswith("-nvidia-open")]
    if missing:
        return Result(FAIL, f"{want} is missing: {', '.join(missing)}"
                      + (" (without it, the NVIDIA driver won't load)." if any("nvidia" in m for m in missing) else "."),
                      Fix(f"Installed {', '.join(missing)}", [f"sudo pacman -S --needed {' '.join(missing)}"],
                          after="Reboot afterwards."))
    others = [k for k in have if k != want]
    if others:
        if running in others:
            return Result(WARN, f"Running {running}, but this laptop should only have {want}.",
                          manual=f"Reboot and choose {want} in the boot menu, then run Checkup again to remove {', '.join(others)}.")
        pkgs = [p for k in others for p in (k, f"{k}-headers", f"{k}-nvidia", f"{k}-nvidia-open") if pkg_version(p)]
        return Result(WARN, f"Extra kernel{'s' if len(others) > 1 else ''} installed: {', '.join(others)}. "
                      f"This laptop uses only {want}.",
                      Fix(f"Removed extra kernels ({', '.join(others)})", [f"sudo pacman -Rns {' '.join(pkgs)}"],
                          danger="Only the kernel you're running now is kept."))
    if running and running != want:
        return Result(WARN, f"Running {running}, expected {want}.", manual="Reboot to start the right kernel.")
    return Result(OK, f"Only {want} is installed" + (" with its NVIDIA module." if nvidia else "."))


ERSM_TOOL = "tools/er-save-manager-update"
ERSM_TARGET = HOME / ".local/bin/er-save-manager-update"


def _ersm_source():
    for base in (repo_dir(), Path("/usr/share/checkup"), Path(__file__).resolve().parent.parent):
        if (base / ERSM_TOOL).exists():
            return base / ERSM_TOOL
    return None


def c_er_save_manager(ctx):
    if not ctx.expects("er-save-manager"):
        return None
    src = _ersm_source()
    installed = ERSM_TARGET.exists()
    app = DATA_DIR / "er-save-manager/ER-Save-Manager.AppImage"   # running the updater moves an old ~/Applications copy here
    desktop = HOME / ".local/share/applications/er-save-manager.desktop"
    if not src:
        return Result(SKIP, "The updater script isn't available (update ~/.local/src/stability-tester or Checkup).")
    current = installed and read(ERSM_TARGET) == read(src)
    script = []
    if not current:
        script.append(f"install -Dm755 {shell_quote(src)} {shell_quote(ERSM_TARGET)}")
    if not current or not app.exists() or "--launch" not in read(desktop):
        script.append(f"{shell_quote(ERSM_TARGET)}")
    if not script:
        return Result(OK, "The Elden Ring Save Manager is installed and updates itself.")
    problem = ("the updater isn't installed" if not installed else "the updater is out of date" if not current
               else "the Save Manager or its app menu entry is missing")
    return Result(FAIL, _cap(problem) + ".", Fix("Installed the Elden Ring Save Manager updater", script))


def c_secure_boot(ctx):
    if not which("sbctl"):
        if ctx.expects("secure-boot"):
            return Result(INFO, "sbctl isn't installed, so Secure Boot isn't set up with your own keys.",
                          manual="Secure Boot setup needs BIOS steps (Setup Mode) and can't be automated safely. "
                                 "Follow the CachyOS wiki's Secure Boot page, then run Checkup again.")
        return None
    if not ctx.root.get("_ok"):
        return Result(SKIP, "Needs administrator access to read Secure Boot status.")
    status = ctx.root.get("sbctl_status", "")
    if "Secure Boot" in status and "Enabled" not in status.split("Secure Boot", 1)[1].split("\n", 1)[0]:
        return Result(INFO, "Secure Boot is off, so nothing needs signing.")
    unsigned = []
    for line in ctx.root.get("sbctl_verify", "").splitlines():
        if "✗" in line or "not signed" in line:
            path = line.split("✗")[-1].strip().split(" is not signed")[0].strip()
            if path.startswith("/"):
                unsigned.append(path)
    if unsigned:
        return Result(FAIL, "Not signed (the laptop won't boot them): " + ", ".join(unsigned), Fix(
            "Signed the unsigned boot files with sbctl",
            [f"sudo sbctl sign -s {shell_quote(p)}" for p in unsigned] + ["sudo sbctl verify"]))
    return Result(OK, "Secure Boot is on and every boot file is signed.")


def c_default_terminal(ctx):
    if not which("kwriteconfig6"):
        return None
    if not ctx.expects("terminal") and pkg_version("konsole"):
        return None
    value = kread("kdeglobals", "General", "TerminalApplication")
    if "alacritty" in value.lower():
        return Result(OK, "Alacritty is the default terminal.")
    script = [] if pkg_version("alacritty") else ["sudo pacman -S --needed alacritty"]
    script += [kwrite_cmd("kdeglobals", "General", "TerminalApplication", "alacritty"),
               kwrite_cmd("kdeglobals", "General", "TerminalService", "Alacritty.desktop")]
    return Result(FAIL, f"The default terminal is '{value or 'Konsole'}', not Alacritty.",
                  Fix("Set Alacritty as KDE's default terminal", script))


def c_konsole(ctx):
    if not ctx.expects("konsole"):
        return None
    if not pkg_version("konsole"):
        return Result(OK, "Konsole is removed, as you chose.")
    needed_by = pkg_required_by("konsole")
    if needed_by:
        return Result(WARN, "Konsole is installed again.",
                      manual=f"It's needed by: {', '.join(needed_by)}. Remove those first, or ignore this check.")
    return Result(WARN, "Konsole is installed again.", Fix(
        "Removed Konsole again", ["sudo pacman -Rns konsole"],
        danger="Make sure Alacritty is your default terminal first (the 'Default terminal' check)."))


def c_shelly(ctx):
    if not ctx.expects("shelly"):
        return None
    if not pkg_version("shelly"):
        return Result(OK, "Shelly is removed, as you chose.")
    pkgs = "shelly shelly-flatpak-backend" if pkg_version("shelly-flatpak-backend") else "shelly"
    return Result(WARN, "Shelly is installed again.", Fix("Removed Shelly again", [f"sudo pacman -Rns {pkgs}"]))


def c_fastfetch(ctx):
    config = HOME / ".config/fish/config.fish"
    text = read(config)
    if not ctx.expects("fastfetch") and "fastfetch" not in text:
        return None
    shell = login_shell()
    missing = [p for p in ("fastfetch", "alacritty") if not pkg_version(p)]
    problems = fixers.fish_fastfetch_problems(text)
    if not shell.endswith("fish"):
        return Result(WARN, f"Your login shell is {shell}, but the greeting is set up for fish.",
                      manual="Run 'chsh -s /usr/bin/fish', or ask for the bash version of the greeting.")
    if not missing and not problems:
        return Result(OK, "fastfetch with the CachyOS logo opens in every terminal.")

    new_text = fixers.fish_fastfetch_fix(text)

    def apply():
        config.parent.mkdir(parents=True, exist_ok=True)
        if config.exists():
            backup = config.with_name(f"config.fish.checkup-backup-{time.strftime('%Y%m%d-%H%M%S')}")
            backup.write_text(text)
        config.write_text(new_text)
        return f"Rewrote {config} (backup saved next to it)."

    detail = "; ".join(([f"not installed: {', '.join(missing)}"] if missing else []) + problems)
    return Result(FAIL, _cap(detail) + ".", Fix(
        "Repaired the fastfetch greeting in fish",
        [f"sudo pacman -S --needed {' '.join(missing)}"] if missing else [],
        python=apply if problems else None,
        preview=f"New {config}:\n\n{new_text}"))


def c_docker(ctx):
    installed = pkg_version("docker")
    if not installed and not ctx.expects("docker"):
        return None
    script, problems, after = [], [], ""
    if not installed:
        problems.append("Docker isn't installed")
        script.append("sudo pacman -S --needed docker")
    enabled, active = unit_state("docker.service")
    if enabled != "enabled" or active != "active":
        problems.append(f"the Docker service is {active}" + ("" if enabled == "enabled" else " and not enabled at boot"))
        script.append("sudo systemctl enable --now docker.service")
    if "docker" not in groups_configured():
        problems.append(f"{USER} isn't in the docker group")
        script.append(f"sudo usermod -aG docker {USER}")
        after = "Log out and back in so the group change applies."
    if problems:
        return Result(FAIL, _cap("; ".join(problems)) + ".", Fix("Installed/enabled Docker and joined the docker group", script, after=after))
    if "docker" not in groups_in_session():
        return Result(WARN, "You're in the docker group, but this login session started before that.",
                      manual="Log out and back in (or reboot).")
    return Result(OK, "Docker is running and you're in the docker group.")


def c_vlc(ctx):
    if not pkg_version("vlc"):
        if ctx.expects("vlc"):
            return Result(FAIL, "VLC isn't installed.", Fix(
                "Installed VLC with all its plugins", ["sudo pacman -S --needed vlc vlc-plugins-all"]))
        return None
    codec = Path("/usr/lib/vlc/plugins/codec")
    missing = [name for name, f in (("h264/ffmpeg", "libavcodec_plugin.so"), ("DTS", "libdca_plugin.so"))
               if not (codec / f).exists()]
    if missing:
        return Result(FAIL, f"VLC can't play: {', '.join(missing)}.", Fix(
            "Installed all VLC plugins", ["sudo pacman -S --needed vlc-plugins-all", "rm -rf ~/.cache/vlc"]))
    return Result(OK, "VLC has its h264 and DTS decoders.")


def c_ntfsprogs(ctx):
    if not ctx.expects("ntfsprogs") and not any(l.split()[2:3] in (["ntfs3"], ["ntfs"]) for l in read("/etc/fstab").splitlines() if l.strip() and not l.startswith("#")):
        return None
    if which("ntfsfix"):
        return Result(OK, "ntfsfix is available for repairing NTFS drives.")
    return Result(FAIL, "ntfsfix isn't installed.", Fix("Installed ntfsprogs", ["sudo pacman -S --needed ntfsprogs"]))


def c_windows_drive(ctx):
    if not ctx.expects("windows-drive"):
        return None
    WINDOWS_UUID = windows_partition(ctx)
    if not WINDOWS_UUID:
        return Result(SKIP, "No Windows (NTFS) partition found on this computer.")
    dev = Path(f"/dev/disk/by-uuid/{WINDOWS_UUID}")
    real = os.path.realpath(dev)
    fstab = read("/etc/fstab")
    problems = fixers.fstab_problems(fstab, WINDOWS_UUID)
    if problems:
        new = fixers.fstab_fix(fstab, WINDOWS_UUID, WINDOWS_MOUNT, UID, GID)
        tmp = HOME / ".cache/checkup/fstab.new"
        stamp = time.strftime("%Y%m%d-%H%M%S")

        def write_tmp():
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(new)
            return "Prepared the corrected fstab."

        return Result(FAIL, _cap("; ".join(problems)) + ".", Fix(
            "Corrected the Windows drive's line in /etc/fstab",
            [f"sudo cp /etc/fstab /etc/fstab.checkup-backup-{stamp}",
             f"sudo install -m 644 {tmp} /etc/fstab",
             f"sudo mkdir -p {WINDOWS_MOUNT}",
             "sudo systemctl daemon-reload",
             "sudo mount -a"],
            python=write_tmp, preview=f"New /etc/fstab:\n\n{new}"))

    rc, _, _ = run(["findmnt", "-S", f"UUID={WINDOWS_UUID}"])
    if rc == 0:
        return Result(OK, f"Mounted at {WINDOWS_MOUNT} and set to mount at boot.")
    klog = ctx.root.get("kernel_log", "")
    name = os.path.basename(real)
    if f"ntfs3({name})" in klog and "dirty" in klog:
        return Result(FAIL, "The drive is marked dirty by Windows, so Linux won't mount it.", Fix(
            "Cleared the dirty flag with ntfsfix and mounted the drive",
            ["sudo pacman -S --needed ntfsprogs", f"sudo ntfsfix -d {real}", "sudo mount -a"],
            danger="Safer option: boot Windows, run 'chkdsk C: /f', turn off Fast Startup and shut down fully. "
                   "ntfsfix only clears the flag; it doesn't repair the filesystem."))
    return Result(FAIL, "The drive is set up in fstab but isn't mounted.",
                  Fix("Mounted the Windows drive", [f"sudo mkdir -p {WINDOWS_MOUNT}", "sudo mount -a"]))


def c_usb_automount(ctx):
    autostart = HOME / ".config/autostart/udiskie.desktop"
    if autostart.exists() and which("udiskie"):
        return Result(OK, "udiskie mounts USB drives when you plug them in.")
    if not which("kwriteconfig6"):
        return None
    keys = {k: kread("kded_device_automounterrc", "General", k).lower()
            for k in ("AutomountEnabled", "AutomountOnLogin", "AutomountOnPlugin")}
    if keys["AutomountOnPlugin"] == "true" and keys["AutomountOnLogin"] == "true" and keys["AutomountEnabled"] != "false":
        return Result(OK, "KDE mounts USB drives on login and when plugged in.")
    if not ctx.expects("usb-automount") and not any(keys.values()):
        return None
    return Result(FAIL, "KDE isn't set to auto-mount USB drives.", Fix(
        "Turned on KDE's USB drive auto-mounting",
        [kwrite_cmd("kded_device_automounterrc", "General", k, "true")
         for k in ("AutomountEnabled", "AutomountOnLogin", "AutomountOnPlugin")],
        after="Reboot so KDE picks it up (a KDE bug hides the device list until then)."))


def c_webcam_page(ctx):
    installed = pkg_version("kcm-webcam")
    if not installed and not ctx.expects("webcam-page"):
        return None
    if installed:
        return Result(OK, f"Webcam settings page installed ({upstream(installed)}).")
    return Result(FAIL, "The Webcam settings page isn't installed.", Fix(
        "Installed the Webcam settings page from GitHub",
        ["sudo pacman -S --needed git base-devel",
         "mkdir -p ~/.local/src && if [ -d ~/kcm-webcam/.git ] && [ ! -e ~/.local/src/kcm-webcam ]; then mv ~/kcm-webcam ~/.local/src/; fi",
         "if [ -d ~/.local/src/kcm-webcam/.git ]; then git -C ~/.local/src/kcm-webcam pull; else git clone https://github.com/mrichman45/kcm-webcam ~/.local/src/kcm-webcam; fi",
         "@build ~/.local/src/kcm-webcam",
         "systemctl --user daemon-reload",
         "systemctl --user enable --now webcam-settings.service"]))


def c_webcam_service(ctx):
    if not pkg_version("kcm-webcam"):
        return None
    enabled, active = unit_state("webcam-settings.service", user=True)
    if enabled == "enabled" and active == "active":
        return Result(OK, "Your webcam settings are restored at login and when the camera switches on.")
    return Result(FAIL, f"The webcam settings service is {active}" + ("" if enabled == "enabled" else ", not enabled") + ".",
                  Fix("Enabled the webcam settings service",
                      ["systemctl --user daemon-reload", "systemctl --user enable --now webcam-settings.service"]))


def c_camera(ctx):
    if not ctx.expects("camera"):
        return None
    names = [read(f"{d}/name").strip() for d in sorted(Path("/sys/class/video4linux").glob("video*"))]
    if names:
        return Result(OK, f"Camera detected: {names[0]}.")
    return Result(WARN, "No camera detected.",
                  manual="Slide the camera switch on the right side of the laptop to on. If it's on, check the BIOS (F2).")


def c_nordvpn(ctx):
    # Only checked on a laptop whose profile lists it (none do by default).
    if not ctx.expects("nordvpn"):
        return None
    script, problems, after = [], [], ""
    if not (pkg_version("nordvpn-bin") or pkg_version("nordvpn")):
        problems.append("NordVPN isn't installed")
        script += ["sudo pacman -S --needed git base-devel", "@aur nordvpn-bin"]
    enabled, active = unit_state("nordvpnd.service")
    if enabled != "enabled" or active != "active":
        problems.append(f"the NordVPN service is {active}")
        script.append("sudo systemctl enable --now nordvpnd")
    if "nordvpn" not in groups_configured():
        problems.append(f"{USER} isn't in the nordvpn group")
        script.append(f"sudo usermod -aG nordvpn {USER}")
        after = "Log out and back in."
    if problems:
        return Result(FAIL, _cap("; ".join(problems)) + ".", Fix("Enabled NordVPN's service and group", script, after=after))
    return Result(OK, "NordVPN service running and you're in the nordvpn group.")


def c_extras(ctx):
    e = getattr(ctx.machine, "extras", {}) or {}
    if not any(e.get(k) for k in ("packages", "aur", "flatpaks", "remove", "services", "user_services", "groups", "shell", "notes")):
        return None
    script, problems, after, manual = [], [], [], []
    missing = [p for p in e.get("packages", []) if not pkg_version(p)]
    if missing:
        problems.append("apps not installed: " + ", ".join(missing))
        script.append("sudo pacman -S --needed " + " ".join(missing))
    missing_aur = [p for p in e.get("aur", []) if not pkg_version(p)]
    if missing_aur:
        problems.append("AUR apps not installed: " + ", ".join(missing_aur))
        script += ["sudo pacman -S --needed git base-devel"] + [f"@aur {p}" for p in missing_aur]
    if e.get("flatpaks"):
        have = set(run(["flatpak", "list", "--app", "--columns=application"])[1].split()) if which("flatpak") else set()
        missing_fp = [a for a in e["flatpaks"] if a not in have]
        if missing_fp:
            problems.append("Flatpaks not installed: " + ", ".join(missing_fp))
            script += ["sudo pacman -S --needed flatpak",
                       "sudo flatpak remote-add --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo"]
            script += [f"sudo flatpak install -y --noninteractive flathub {a}" for a in missing_fp]
    back = [p for p in e.get("remove", []) if pkg_version(p)]
    removable = [p for p in back if not pkg_required_by(p)]
    if back:
        problems.append("removed apps are back: " + ", ".join(back))
        if removable:
            script.append("sudo pacman -Rns " + " ".join(removable))
        if len(removable) < len(back):
            manual.append("Some removed apps are needed by other packages: " + ", ".join(sorted(set(back) - set(removable))))
    for unit in e.get("services", []):
        enabled, active = unit_state(unit)
        if enabled != "enabled" or active != "active":
            problems.append(f"{unit} is {active}")
            script.append(f"sudo systemctl enable --now {unit}")
    for unit in e.get("user_services", []):
        enabled, active = unit_state(unit, user=True)
        if enabled != "enabled" or active != "active":
            problems.append(f"your {unit} is {active}")
            script += ["systemctl --user daemon-reload", f"systemctl --user enable --now {unit}"]
    missing_groups = [g for g in e.get("groups", []) if g not in groups_configured()]
    if missing_groups:
        problems.append("not in groups: " + ", ".join(missing_groups))
        script += [f"sudo groupadd -f {g}" for g in missing_groups] + [f"sudo usermod -aG {g} {USER}" for g in missing_groups]
        after.append("Log out and back in so the group changes apply.")
    if e.get("shell") and not login_shell().endswith("/" + e["shell"]):
        problems.append(f"login shell isn't {e['shell']}")
        script += [f"sudo pacman -S --needed {e['shell']}", f"sudo chsh -s /usr/bin/{e['shell']} {USER}"]
        after.append("Log out and back in to use the new shell.")
    texts = e.get("note_text", {})
    manual += [texts.get(n, n) for n in e.get("notes", [])]
    total = sum(len(e.get(k, [])) for k in ("packages", "aur", "flatpaks", "remove", "services", "user_services", "groups"))
    if not problems:
        return Result(OK, f"All {total} apps and settings found earlier on this laptop are in place.",
                      manual=" ".join(manual))
    return Result(FAIL, _cap("; ".join(problems)) + ".",
                  Fix("Restored apps and settings found on this laptop", script, after=" ".join(after)),
                  manual=" ".join(manual))


def c_dns(ctx):
    times = []
    for host in ("archlinux.org", "wikipedia.org", "github.com"):
        t0 = time.monotonic()
        try:
            socket.getaddrinfo(host, 443)
        except OSError:
            return Result(WARN, f"Couldn't look up {host}: no internet, or DNS isn't answering.",
                          manual="Check Wi-Fi. On airplane Wi-Fi, log in to the airline's page first.")
        times.append((time.monotonic() - t0) * 1000)
    slowest = max(times)
    if slowest > 1000:
        return Result(WARN, f"Name lookups are slow (up to {slowest:.0f} ms).",
                      manual="Normal on airplane Wi-Fi. Elsewhere, restart the router, or set DNS to 1.1.1.1 in the Wi-Fi connection's IPv4 settings.")
    return Result(OK, f"Name lookups take {slowest:.0f} ms at most.")


CHECKS = [
    # Order matters for "Set up this laptop": updates first, then packages, then settings.
    Check("updates", "System up to date", "reading-an-update-list", c_updates),
    Check("nvidia", "NVIDIA driver versions match", "nvidia-mismatch", c_nvidia),
    Check("reboot", "Kernel update finished (rebooted)", "reading-an-update-list", c_reboot),
    Check("kernel", "One kernel, with its NVIDIA module", "kernel", c_kernel),
    Check("secure-boot", "Secure Boot files signed", "secure-boot", c_secure_boot),
    Check("terminal", "Alacritty is the default terminal", "konsole", c_default_terminal),
    Check("konsole", "Konsole stays removed", "konsole", c_konsole, preference=True),
    Check("shelly", "Shelly stays removed", "shelly-remove", c_shelly, preference=True),
    Check("fastfetch", "fastfetch greeting in fish", "fastfetch", c_fastfetch),
    Check("docker", "Docker running and usable", "docker", c_docker),
    Check("vlc", "VLC can play h264 and DTS", "vlc", c_vlc),
    Check("ntfsprogs", "NTFS repair tool installed", "ntfs", c_ntfsprogs),
    Check("windows-drive", "Windows drive mounts at boot", "ntfs-automount", c_windows_drive),
    Check("usb-automount", "USB drives auto-mount", "usb-automount", c_usb_automount),
    Check("camera", "Camera detected (switch on)", "webcam", c_camera),
    Check("webcam-page", "Webcam settings page installed", "kcm-webcam", c_webcam_page),
    Check("webcam-service", "Webcam settings restored automatically", "kcm-webcam", c_webcam_service),
    Check("nordvpn", "NordVPN ready", "nordvpn", c_nordvpn),
    Check("er-save-manager", "Elden Ring Save Manager updates itself", "elden-ring", c_er_save_manager),
    Check("extras", "Apps and settings found on this laptop", "also-set-up-on-this-laptop-found-by-checkup", c_extras),
    Check("dns", "Internet name lookups", "dns", c_dns),
]


def run_checks(ctx, ignored=(), progress=None):
    """Run every check; returns [(Check, Result)] for checks that apply."""
    ctx.gather_root(which("sbctl") or ctx.expects("windows-drive"))
    results = []
    for i, check in enumerate(CHECKS):
        if progress:
            progress(i, len(CHECKS), check.title)
        if check.id in ignored:
            results.append((check, Result(SKIP, "Ignored (you chose not to check this).")))
            continue
        try:
            res = check.func(ctx)
        except Exception as e:  # a broken check shouldn't stop the others
            res = Result(WARN, f"Check couldn't run: {e}")
        if res is not None:
            results.append((check, res))
    if ctx.cfg is not None:   # remembers things found on this laptop (e.g. the Windows partition)
        from .guide import save_config
        save_config(ctx.cfg)
    return results
