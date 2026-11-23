"""Small helpers shared by the checks, the stability tests and the app."""

import grp
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path

HOME = Path.home()
USER = pwd.getpwuid(os.getuid()).pw_name
UID = os.getuid()
GID = os.getgid()

SRC_DIR = HOME / ".local/src"            # where source folders live (hidden, out of the way)
DATA_DIR = HOME / ".local/share"


def repo_dir():
    """The stability-tester clone: ~/.local/src/stability-tester, or the old ~/stability-tester."""
    for d in (SRC_DIR / "stability-tester", HOME / "stability-tester"):
        if (d / ".git").exists():
            return d
    return SRC_DIR / "stability-tester"


HELPER_INSTALLED = Path("/usr/lib/checkup/checkup-root")
HELPER_DEV = Path(__file__).resolve().parent.parent / "checkup-root"


def run(cmd, timeout=30, env=None, input=None):
    """Run a command; return (returncode, stdout, stderr). Never raises for missing programs."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env, input=input)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def which(name):
    return shutil.which(name) is not None


def read(path, default=""):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return default


# ---------- pacman ----------

def pkg_version(name):
    """Installed version of a package, or None."""
    rc, out, _ = run(["pacman", "-Q", name])
    if rc != 0:
        return None
    parts = out.split()
    return parts[1] if len(parts) >= 2 else None


def pkg_required_by(name):
    rc, out, _ = run(["pacman", "-Qi", name])
    if rc != 0:
        return []
    m = re.search(r"^Required By\s*:\s*(.+)$", out, re.M)
    if not m or m.group(1).strip() == "None":
        return []
    return m.group(1).split()


def repo_versions(name):
    """[(repo, version)] for a package in the sync databases, highest priority first."""
    rc, out, _ = run(["pacman", "-Si", name])
    if rc != 0:
        return []
    result, repo = [], None
    for line in out.splitlines():
        m = re.match(r"^Repository\s*:\s*(\S+)", line)
        if m:
            repo = m.group(1)
            continue
        m = re.match(r"^Version\s*:\s*(\S+)", line)
        if m and repo:
            result.append((repo, m.group(1)))
            repo = None
    return result


def upstream(version):
    """'1:620.73.04-1.1' -> '620.73.04' (drops epoch and package release)."""
    if not version:
        return ""
    v = version.split(":", 1)[-1]
    return v.rsplit("-", 1)[0]


# ---------- systemd ----------

def unit_state(unit, user=False):
    base = ["systemctl"] + (["--user"] if user else [])
    _, enabled, _ = run(base + ["is-enabled", unit])
    _, active, _ = run(base + ["is-active", unit])
    return enabled.strip() or "unknown", active.strip() or "unknown"


# ---------- users and groups ----------

def groups_configured():
    """Groups the user is a member of in /etc/group (takes effect at next login)."""
    rc, out, _ = run(["id", "-nG", USER])
    return set(out.split()) if rc == 0 else set()


def groups_in_session():
    names = set()
    for gid in os.getgroups():
        try:
            names.add(grp.getgrgid(gid).gr_name)
        except KeyError:
            pass
    return names


def login_shell():
    return pwd.getpwuid(UID).pw_shell


# ---------- KDE config ----------

def kread(file, group, key):
    if which("kreadconfig6"):
        rc, out, _ = run(["kreadconfig6", "--file", file, "--group", group, "--key", key])
        if rc == 0:
            return out.strip()
    # Fallback: parse the ini file ourselves.
    text = read(HOME / ".config" / file)
    current = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1]
        elif current == group and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return ""


def kwrite_cmd(file, group, key, value):
    return f"kwriteconfig6 --file {file} --group {group} --key {key} {value}"


# ---------- root helper ----------

def helper_path():
    return str(HELPER_INSTALLED if HELPER_INSTALLED.exists() else HELPER_DEV)


def shell_quote(s):
    return "'" + str(s).replace("'", "'\\''") + "'"
