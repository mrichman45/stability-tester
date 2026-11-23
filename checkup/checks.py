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
    optional: bool = False    # unticked in "Set up this laptop" unless you tick it


class Context:
    def __init__(self, machine, gui=False, cfg=None):
        self.machine = machine
        self.gui = gui
        self.cfg = cfg
        self.root = {}        # filled by gather_root()
        self.step_vals = {}   # placeholder values on this laptop (guide steps)
        self.step_root = {}   # root test results for guide steps

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


TAS_REPO = "https://github.com/DanielWeiner/tas2781-fix-16IRX8H"
TAS_DIR = SRC_DIR / "tas2781-fix-16IRX8H"


def c_speakers(ctx):
    """Lenovo Legion speaker amplifier (TI TAS2781) fix, from DanielWeiner/tas2781-fix-16IRX8H."""
    if not ctx.expects("speakers"):
        return None
    script = Path("/usr/local/bin/tas2781-fix")
    system_unit = Path("/etc/systemd/system/tas2781-fix.service")
    enabled, _ = unit_state("tas2781-fix.service", user=True)
    problems = []
    if not script.exists():
        problems.append("the speaker fix isn't installed")
    elif not system_unit.exists():
        problems.append("the speaker fix's system service is missing")
    elif enabled != "enabled":
        problems.append("the speaker fix isn't switched on for your login")
    missing = [p for p in ("jq", "i2c-tools") if not pkg_version(p)]
    if missing:
        problems.append("it needs " + " and ".join(missing))
    if not problems:
        return Result(OK, "The speaker amplifier fix is installed and runs at login and after sleep.")
    d = shell_quote(TAS_DIR)
    fix = ["sudo pacman -S --needed git jq i2c-tools"]
    if not script.exists() or not system_unit.exists():
        fix += [f"mkdir -p {shell_quote(SRC_DIR)} && if [ -d {d}/.git ]; then git -C {d} pull --ff-only; "
                f"else git clone {TAS_REPO} {d}; fi",
                f"sudo bash \"$(find {d} -maxdepth 1 -type f -name 'tas2781-fix*' ! -name '*.md' | head -n1)\" --install"]
    fix += ["systemctl --user daemon-reload", "systemctl --user enable --now tas2781-fix.service"]
    return Result(FAIL, _cap("; ".join(problems)) + " (without it, the speakers may be silent or quiet).",
                  Fix("Installed the Legion speaker fix (tas2781-fix)", fix, after="Restart, then test the speakers."))


# ---------------------------------------------------------------- custom Legion services

LEGION_BUNDLE = "tools/legion"
TEST_ROOT = os.environ.get("CHECKUP_TEST_ROOT", "")   # tests only: where "/" files live


def _bundle_dir():
    for base in (repo_dir(), Path("/usr/share/checkup"), Path(__file__).resolve().parent.parent):
        if (base / LEGION_BUNDLE / "manifest.json").exists():
            return base / LEGION_BUNDLE
    return None


def _dest(path):
    if path.startswith("~/"):
        return HOME / path[2:]
    return Path(TEST_ROOT + path)


def _ntfs_uuid(ctx):
    """The NTFS data drive: the biggest NTFS partition that isn't on the disk CachyOS runs from."""
    from .steps import values
    return values(ctx).get("NTFS_UUID", "")


def _render(text, ctx):
    """Repo copy -> what belongs on this laptop (fill in the placeholders)."""
    return text.replace("__USER__", USER).replace("__NTFS_UUID__", _ntfs_uuid(ctx))


def _scrub(text, ctx):
    """Laptop copy -> what goes in the public repo (personal details back to placeholders)."""
    text = re.sub(r"^DESKTOP_USER=.*$", "DESKTOP_USER=__USER__", text, flags=re.M)
    return re.sub(r'^UUID="[0-9A-Fa-f-]+"', 'UUID="__NTFS_UUID__"', text, flags=re.M)


def legion_bundle_state(ctx):
    """[(entry, state)] with state ok | missing | changed (edited on this laptop)."""
    bundle = _bundle_dir()
    if not bundle:
        return None, []
    manifest = json.loads((bundle / "manifest.json").read_text())
    out = []
    for e in manifest["files"]:
        dest = _dest(e["dest"])
        if not dest.exists():
            out.append((e, "missing"))
            continue
        repo = (bundle / e["src"]).read_text()
        here = read(dest)
        out.append((e, "ok" if _scrub(here, ctx) == _scrub(repo, ctx) else "changed"))
    return manifest, out


def c_legion_services(ctx):
    if not ctx.expects("legion-services"):
        return None
    manifest, files = legion_bundle_state(ctx)
    if manifest is None:
        return Result(SKIP, "The Legion services bundle isn't available (update ~/.local/src/stability-tester).")
    bundle = _bundle_dir()
    missing = [e for e, s in files if s == "missing"]
    changed = [e for e, s in files if s == "changed"]
    units_off = [u for u in manifest["enable"]
                 if Path(f"/usr/lib/systemd/system/{u}").exists() or Path(f"/etc/systemd/system/{u}").exists()
                 if unit_state(u)[0] != "enabled"]
    units_on = [u for u in manifest["disable"] if unit_state(u)[0] == "enabled"]
    user_off = [u for u in manifest["enable_user"] if unit_state(u, user=True)[0] != "enabled"]
    pkgs = [p for p in manifest["packages"] if not pkg_version(p)]

    if missing or units_off or units_on or user_off or pkgs:
        stage = HOME / ".cache/checkup/legion"
        script, problems = [], []
        if pkgs:
            problems.append("missing packages: " + ", ".join(pkgs))
            script.append("sudo pacman -S --needed " + " ".join(pkgs))
        if missing:
            problems.append("not installed: " + ", ".join(Path(e["dest"]).name for e in missing))
            for e in missing:
                src = shell_quote(stage / e["src"])
                dest = e["dest"]
                if e.get("root"):
                    script.append(f"sudo install -Dm{e['mode']} {src} {shell_quote(dest)}")
                else:
                    script.append(f"install -Dm{e['mode']} {src} {shell_quote(_dest(dest))}")
            script.append("sudo systemctl daemon-reload")
            script += [e["after"] for e in missing if e.get("after")]
        if units_off:
            problems.append("services off: " + ", ".join(units_off))
        if units_on:
            problems.append("should be off: " + ", ".join(units_on))
        script += [f"sudo systemctl enable --now {u}" for u in units_off]
        script += [f"sudo systemctl disable --now {u}" for u in units_on]
        if user_off:
            problems.append("your services off: " + ", ".join(user_off))
            script += ["systemctl --user daemon-reload"] + [f"systemctl --user enable --now {u}" for u in user_off]

        def stage_files():
            stage.mkdir(parents=True, exist_ok=True)
            for e in missing:
                (stage / e["src"]).write_text(_render((bundle / e["src"]).read_text(), ctx))
            return f"Prepared {len(missing)} files (your username and drive filled in)."

        note = f" {len(changed)} other file(s) were edited on this laptop and are left alone." if changed else ""
        return Result(FAIL, _cap("; ".join(problems)) + "." + note,
                      Fix("Restored the custom Legion services", script, python=stage_files if missing else None,
                          after="Restart so the power and audio services start cleanly."))

    if changed:
        names = ", ".join(Path(e["dest"]).name for e in changed)

        def save_to_repo():
            for e in changed:
                (bundle / e["src"]).write_text(_scrub(read(_dest(e["dest"])), ctx))
            return f"Saved {len(changed)} file(s) into {bundle}. Press Sync with GitHub to share them."

        return Result(WARN, f"Edited on this laptop since the repo copy: {names}. "
                            "Save them to the repo so a reinstall gets these versions.",
                      Fix("Saved this laptop's Legion services to the repo", [], python=save_to_repo,
                          preview="Personal details (your username, drive ID) are replaced with placeholders before saving."))
    return Result(OK, f"All {len(files)} custom Legion files are installed, match the repo, and their services are on.")


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
    Check("speakers", "Speaker fix installed", "speakers", c_speakers),
    Check("legion-services", "Legion services (power, audio, GPU)", "legion-services", c_legion_services),
    Check("extras", "Apps and settings found on this laptop", "also-set-up-on-this-laptop-found-by-checkup", c_extras),
    Check("dns", "Internet name lookups", "dns", c_dns),
]


# ---------------------------------------------------------------- the laptop guide's own steps

def _slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def step_check(step):
    from . import steps as S

    def func(ctx):
        vals = ctx.step_vals
        if step.when:
            rc, _ = S.test_user(step, vals, step.when + " >/dev/null 2>&1")
            if rc != 0:
                return None
        if step.check_as == "root":
            if step.id not in ctx.step_root:
                return Result(SKIP, "Needs your password to check (press Run checks again and authenticate).")
            rc, msg = ctx.step_root[step.id]
        else:
            rc, msg = S.test_user(step, vals)
        if rc == 0:
            changes = S.capture_changes(step, vals)
            if changes:
                names = ", ".join(d for d, _ in changes[:4]) + (" …" if len(changes) > 4 else "")
                return Result(WARN, f"Done, and this laptop has settings the repo doesn't: {names}.",
                              Fix(f"Saved {step.title.lower()} settings to the repo", [],
                                  python=lambda: f"Saved {S.save_captures(step, vals, changes)} file(s). "
                                                 "Press Sync with GitHub to share them.",
                                  preview="Your username, drive IDs and network are replaced with placeholders."))
            return Result(OK, "Done.")
        if rc == 3 and msg.startswith("differs:"):   # a file you changed on this laptop
            repo_file, here = msg[len("differs:"):].split("|", 1)
            name = Path(here).name

            def save():
                Path(repo_file).write_text(S.scrub(Path(here).read_text(), vals))
                return f"Saved your {name} into the repo. Press Sync with GitHub to share it."
            dest = here.replace(str(HOME), "~", 1)
            use_guide = (f"sudo install -m644 {shell_quote(repo_file)} {shell_quote(here)}" if not here.startswith(str(HOME))
                         else f"install -m644 {shell_quote(repo_file)} {dest}")
            return Result(WARN, f"Your {name} is different from the guide's; it's left as it is.",
                          Fix(f"Saved this laptop's {name} to the repo", [], python=save,
                              preview="Your username, drive IDs and network are replaced with placeholders."),
                          manual=f"If the guide's version is the newer one, use it instead: {use_guide}")
        detail = _cap(msg) if msg else "Not done yet."
        if step.default == "manual" or not step.apply:
            return Result(WARN, detail, manual=step.manual or "See this step in the guide.")
        lines = [S.expand(l, step, vals) for l in S.restore_lines(step) + step.apply]
        return Result(FAIL, detail,
                      Fix(step.title, lines, python=lambda: (S.stage(step, vals), "Prepared this step's files.")[1],
                          after=step.after, danger=step.manual if step.default == "off" and step.manual else ""))

    return Check("step:" + step.id, step.title, _slug("Set up this laptop: the guide's steps"), func,
                 optional=step.default == "off")


def all_checks(ctx):
    """The built-in checks, with this laptop's guide steps before the scan's extras."""
    from . import steps as S
    guide_steps = S.load(ctx.machine)
    ctx.step_vals = S.values(ctx) if guide_steps else {}
    roots = [s for s in guide_steps if s.check_as == "root"]
    ctx.step_root = S.test_root_batch(roots, ctx.step_vals, ctx.gui) if roots else {}
    extra = [step_check(s) for s in guide_steps]
    at = next(i for i, c in enumerate(CHECKS) if c.id == "extras")
    return CHECKS[:at] + extra + CHECKS[at:]


def run_checks(ctx, ignored=(), progress=None):
    """Run every check; returns [(Check, Result)] for checks that apply."""
    ctx.gather_root(which("sbctl") or ctx.expects("windows-drive"))
    checks = all_checks(ctx)
    results = []
    for i, check in enumerate(checks):
        if progress:
            progress(i, len(checks), check.title)
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
