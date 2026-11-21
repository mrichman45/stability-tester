"""Find what was set up on this laptop that its guide and profile don't cover yet.

Compares the laptop with how it was right after installing (from /var/log/pacman.log), and
adds what it finds to the laptop's profile ("extras" in machines.json) and its guide, so
"Set up this laptop" can redo it after a reinstall. Nothing personal is written: network shares
are recorded only as placeholders, and nothing is read from your files.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .util import HOME, USER, groups_configured, login_shell, read, run, which

EXTRA_KEYS = ("packages", "aur", "flatpaks", "remove", "services", "user_services", "groups", "shell", "notes")
LOCAL_EXTRAS = HOME / ".config/checkup/extras.json"
CLONE_PROFILES = HOME / "stability-tester/machines.json"

# Installed by Checkup itself, by the guide's own checks, or managed by CachyOS tools.
KNOWN_PACKAGES = {
    "checkup", "kcm-webcam", "docker", "vlc", "vlc-plugins-all", "vlc-plugin-ffmpeg", "fastfetch", "alacritty",
    "ntfsprogs", "nordvpn-bin", "pacman-contrib", "git", "base-devel", "sbctl", "konsole", "shelly",
    "shelly-flatpak-backend", "stress-ng", "memtester", "smartmontools", "glmark2", "mesa-utils", "v4l-utils",
    "pyside6", "polkit", "pciutils",
}
MANAGED = re.compile(r"^(linux|linux-cachyos.*|nvidia.*|lib32-nvidia.*|cachyos-.*|chwd|mkinitcpio.*|"
                     r".*-headers|limine.*|grub|systemd-boot.*|intel-ucode|amd-ucode|.*-firmware.*)$")
KNOWN_SERVICES = {"docker.service", "nordvpnd.service", "webcam-settings.service"}
DEFAULT_GROUPS = {"wheel", "users", "audio", "video", "storage", "optical", "network", "power", "lp", "sys",
                  "input", "rfkill", "autologin", "docker", "nordvpn"}


@dataclass
class Finding:
    key: str        # extras key
    value: str      # package / unit / group / shell / note
    text: str       # human description

    @property
    def id(self):
        return f"{self.key}:{self.value}"


# ---------------------------------------------------------------- what the install looked like

def install_baseline():
    """Packages installed during the first hours of pacman's log (the CachyOS install itself)."""
    first, base = None, set()
    for line in read("/var/log/pacman.log").splitlines():
        m = re.match(r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", line)
        if not m:
            continue
        t = datetime.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S")
        first = first or t
        if t - first > timedelta(hours=6):
            break
        m = re.search(r"\[ALPM\] installed (\S+) ", line)
        if m:
            base.add(m.group(1))
    return base


def removed_by_you():
    """Packages named in 'pacman -R...' commands you ran (pacman.log records the command line)."""
    names = set()
    for line in read("/var/log/pacman.log").splitlines():
        m = re.search(r"\[PACMAN\] Running '(?:\S*/)?pacman (-R\S*)((?: [^']*)?)'", line)
        if m:
            names.update(a for a in m.group(2).split() if not a.startswith("-"))
    return names


def _lines(cmd):
    rc, out, _ = run(cmd, timeout=60)
    return [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []


def _owner(unit, user=False):
    for d in (["/usr/lib/systemd/user", "/etc/systemd/user"] if user else ["/usr/lib/systemd/system", "/etc/systemd/system"]):
        path = Path(d) / unit
        if path.exists():
            out = _lines(["pacman", "-Qqo", str(path)])
            return out[0] if out else "(not from a package)"
    return None


# ---------------------------------------------------------------- the scan

def scan(machine, extras, ignored=()):
    """Return new Findings (not already in the profile, not ignored)."""
    findings = []
    have = {k: set(extras.get(k, []) if k != "shell" else [extras.get("shell", "")]) for k in EXTRA_KEYS}
    covered_checks = set(machine.checks)

    def add(key, value, text):
        f = Finding(key, value, text)
        if value not in have.get(key, set()) and f.id not in ignored:
            findings.append(f)

    baseline = install_baseline()
    explicit = set(_lines(["pacman", "-Qqe"]))
    foreign = set(_lines(["pacman", "-Qqm"]))
    installed = set(_lines(["pacman", "-Qq"]))
    added_pkgs = set()
    if baseline:
        for p in sorted(explicit - baseline):
            if p in KNOWN_PACKAGES or MANAGED.match(p):
                continue
            added_pkgs.add(p)
            if p in foreign:
                add("aur", p, f"{p} (from the AUR or built locally)")
            else:
                add("packages", p, f"{p} (installed after setup)")
        for p in sorted((baseline & removed_by_you()) - installed):
            if p in KNOWN_PACKAGES or MANAGED.match(p):
                continue
            add("remove", p, f"{p} (removed after setup)")

    if which("flatpak"):
        for app in _lines(["flatpak", "list", "--app", "--columns=application"]):
            add("flatpaks", app, f"{app} (Flatpak)")

    for unit in (l.split()[0] for l in _lines(["systemctl", "list-unit-files", "--type=service", "--state=enabled", "--no-legend"])):
        if unit in KNOWN_SERVICES or "@" in unit:
            continue
        owner = _owner(unit)
        if owner and (owner in added_pkgs or owner in foreign or owner == "(not from a package)"):
            add("services", unit, f"{unit} enabled (from {owner})")

    for unit in (l.split()[0] for l in _lines(["systemctl", "--user", "list-unit-files", "--type=service", "--state=enabled", "--no-legend"])):
        if unit in KNOWN_SERVICES or "@" in unit:
            continue
        owner = _owner(unit, user=True)
        if owner and (owner in added_pkgs or owner in foreign or owner == "(not from a package)"):
            add("user_services", unit, f"{unit} enabled for you (from {owner})")

    for g in sorted(groups_configured() - DEFAULT_GROUPS - {USER}):
        add("groups", g, f"member of the '{g}' group")

    shell = Path(login_shell()).name
    if shell not in ("fish", "bash", "") and "fastfetch" not in covered_checks:
        add("shell", shell, f"login shell is {shell}")

    for line in read("/etc/fstab").splitlines():
        fields = line.split()
        if line.lstrip().startswith("#") or len(fields) < 3:
            continue
        if fields[2] in ("cifs", "smb3", "nfs", "nfs4", "sshfs", "fuse.sshfs", "davfs"):
            kind = {"cifs": "Windows/Samba", "smb3": "Windows/Samba", "nfs": "NFS", "nfs4": "NFS"}.get(fields[2], fields[2])
            add("notes", f"network-share-{fields[2]}",
                f"A {kind} network share (`<network-share>`) is mounted at boot from /etc/fstab "
                f"(at `<mount-point>`). Recreate it by hand after a reinstall; it needs the share's address and password.")
    return findings


# ---------------------------------------------------------------- saving

def load_extras(machine_id):
    try:
        local = json.loads(LOCAL_EXTRAS.read_text()).get(machine_id, {})
    except (OSError, json.JSONDecodeError):
        local = {}
    return local


def merged_extras(profile_extras, machine_id):
    out = {k: list(profile_extras.get(k, [])) for k in EXTRA_KEYS if k != "shell"}
    out["shell"] = profile_extras.get("shell", "")
    local = load_extras(machine_id)
    for k in EXTRA_KEYS:
        if k == "shell":
            out["shell"] = local.get("shell") or out["shell"]
        else:
            out[k] = list(dict.fromkeys(out[k] + local.get(k, [])))
    return out


def save_findings(machine, findings):
    """Add findings to the profile: in the GitHub clone's machines.json if there is one (so it syncs),
    otherwise in ~/.config/checkup/extras.json. Returns where it was saved."""
    if not findings:
        return None
    target_clone = CLONE_PROFILES.exists() and (CLONE_PROFILES.parent / ".git").exists() and machine.id != "unknown"
    if target_clone:
        data = json.loads(CLONE_PROFILES.read_text())
        extras = data.setdefault(machine.id, {}).setdefault("extras", {})
    else:
        try:
            data = json.loads(LOCAL_EXTRAS.read_text())
        except (OSError, json.JSONDecodeError):
            data = {}
        extras = data.setdefault(machine.id, {})
    for f in findings:
        if f.key == "shell":
            extras["shell"] = f.value
        else:
            lst = extras.setdefault(f.key, [])
            if f.value not in lst:
                lst.append(f.value)
            if f.key == "notes":
                extras.setdefault("note_text", {})[f.value] = f.text
    for k in list(extras):
        if isinstance(extras[k], list):
            extras[k] = sorted(extras[k])
    if target_clone:
        CLONE_PROFILES.write_text(json.dumps(data, indent=2) + "\n")
        return CLONE_PROFILES
    LOCAL_EXTRAS.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_EXTRAS.write_text(json.dumps(data, indent=2) + "\n")
    return LOCAL_EXTRAS


def remove_items(machine, ids):
    """Take items out of the profile (used by Review). ids like 'packages:foo'."""
    for path, nested in ((CLONE_PROFILES, True), (LOCAL_EXTRAS, False)):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        extras = data.get(machine.id, {}).get("extras", {}) if nested else data.get(machine.id, {})
        changed = False
        for i in ids:
            key, value = i.split(":", 1)
            if key == "shell" and extras.get("shell") == value:
                extras["shell"] = ""
                changed = True
            elif value in extras.get(key, []):
                extras[key].remove(value)
                changed = True
        if changed:
            path.write_text(json.dumps(data, indent=2) + "\n")


def items(extras):
    """All extras as (id, description) for the Review list."""
    out = []
    labels = {"packages": "App", "aur": "AUR app", "flatpaks": "Flatpak", "remove": "Removed",
              "services": "Service", "user_services": "Your service", "groups": "Group"}
    for k, label in labels.items():
        out += [(f"{k}:{v}", f"{label}: {v}") for v in extras.get(k, [])]
    if extras.get("shell"):
        out.append((f"shell:{extras['shell']}", f"Login shell: {extras['shell']}"))
    out += [(f"notes:{n}", "Note: network share") for n in extras.get("notes", [])]
    return out


# ---------------------------------------------------------------- guide section

START = "<!-- checkup:found:start -->"
END = "<!-- checkup:found:end -->"


def guide_section(extras):
    e = extras
    if not any(e.get(k) for k in EXTRA_KEYS):
        return ""
    out = ["## Also set up on this laptop (found by Checkup)", "",
           "Checkup found these on the laptop and added them to its profile, so **Set up this laptop** redoes them "
           "after a reinstall. Remove anything you don't want with **Review** on the My Setup tab.", ""]
    if e.get("packages"):
        out += ["**Apps**", "```bash", "sudo pacman -S --needed " + " ".join(e["packages"]), "```", ""]
    if e.get("aur"):
        out += ["**AUR apps**", "```bash"] + [f"paru -S --needed {p}" for p in e["aur"]] + ["```", ""]
    if e.get("flatpaks"):
        out += ["**Flatpak apps**", "```bash"] + [f"flatpak install -y flathub {a}" for a in e["flatpaks"]] + ["```", ""]
    if e.get("remove"):
        out += ["**Removed after installing**", "```bash", "sudo pacman -Rns " + " ".join(e["remove"]), "```", ""]
    if e.get("services"):
        out += ["**Services**", "```bash"] + [f"sudo systemctl enable --now {s}" for s in e["services"]] + ["```", ""]
    if e.get("user_services"):
        out += ["**Your services**", "```bash"] + [f"systemctl --user enable --now {s}" for s in e["user_services"]] + ["```", ""]
    if e.get("groups"):
        out += ["**Groups** (log out and back in afterwards)", "```bash"] + \
               [f"sudo usermod -aG {g} <your-username>" for g in e["groups"]] + ["```", ""]
    if e.get("shell"):
        out += [f"**Login shell:** `chsh -s /usr/bin/{e['shell']}`", ""]
    if e.get("notes"):
        texts = e.get("note_text", {})
        out += ["**By hand**"] + [f"- {texts.get(n, n)}" for n in e["notes"]] + [""]
    return "\n".join(out).rstrip() + "\n"


def write_guide_section(path, extras):
    text = Path(path).read_text(errors="replace")
    section = guide_section(extras)
    block = f"{START}\n{section}{END}\n" if section else ""
    if START in text and END in text:
        before, rest = text.split(START, 1)
        after = rest.split(END, 1)[1].lstrip("\n")
        text = before + block + ("\n" if block else "") + after
    elif block:
        marker = "\n---\n\n## Fix log"
        text = text.replace(marker, f"\n---\n\n{block}" + marker, 1) if marker in text else text.rstrip() + "\n\n" + block
    Path(path).write_text(text)
