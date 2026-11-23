"""Guide steps: one small bash file per step in a laptop's guide, turned into Checkup checks.

A laptop's profile names its folder ("steps": "steps/legion-i9"). Every NN-id.sh in it is one step:

    # title: Mount the NTFS data drive
    # section: 1. The NTFS data drive          (heading in the guide, for "Open in guide")
    # default: on | off | manual               (off = optional: unticked in Set up this laptop;
    #                                           manual = Checkup can only test it and say what to do)
    # check-as: user | root                    (root tests run in the one administrator session)
    # when: <bash test>                        (skip the step entirely unless this succeeds, run as you)
    # after: Log out and back in.
    # manual: What to do by hand (shown when the test fails).
    # capture: /etc/legion_linux/*.yaml        (files to save from this laptop into the repo, and put
    #                                           back on a reinstall; one glob per line)

    check() {        # exit 0 = done; otherwise print one line saying what's missing
      ...
    }

    apply() {        # one command per line; "sudo ..." runs as root, "@aur PKG" builds from the AUR
    sudo ...
    }

In tests and commands these are set: $R (this step's files, placeholders filled in), $HOME, $USER, $UID, $GID,
$NTFS_UUID (the NTFS data drive), $WINDOWS_UUID (the Windows partition, if any), $LAN_SUBNET (e.g.
the 192.168.x.0/24 your laptop is on). Files under files/ use __USER__, __HOME__, __NTFS_UUID__,
__WINDOWS_UUID__ and __LAN_SUBNET__ so nothing personal is in the repo.
"""

import fnmatch
import glob
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .util import HOME, USER, repo_dir, run

STAGE = HOME / ".cache/checkup/steps"
TEST_ROOT = os.environ.get("CHECKUP_TEST_ROOT", "")   # tests only: where "/" files live


@dataclass
class Step:
    id: str
    path: Path
    title: str
    section: str = ""
    default: str = "on"
    check_as: str = "user"
    when: str = ""
    after: str = ""
    manual: str = ""
    capture: list = field(default_factory=list)
    apply: list = field(default_factory=list)

    @property
    def files(self):
        return self.path.parent / "files" / self.id


def steps_dir(machine):
    rel = getattr(machine, "steps", "") or ""
    if not rel:
        return None
    for base in (repo_dir(), Path("/usr/share/checkup"), Path(__file__).resolve().parent.parent):
        if (base / rel).is_dir():
            return base / rel
    return None


def parse(path):
    text = path.read_text()
    meta = {}
    capture = []
    for line in text.splitlines():
        m = re.match(r"#\s*([a-z-]+):\s?(.*)$", line)
        if not m or line.startswith("#!"):
            if line.strip() and not line.startswith("#"):
                break
            continue
        k, v = m.group(1), m.group(2).strip()
        if k == "capture":
            capture.append(v)
        elif k in meta:            # continued metadata (long manual text)
            meta[k] += " " + v
        else:
            meta[k] = v
    body = re.search(r"^apply\(\)\s*\{\s*\n(.*?)^\}", text, re.M | re.S)
    lines = []
    if body:
        for l in body.group(1).splitlines():
            l = l.strip()
            if l and not l.startswith("#"):
                lines.append(l)
    sid = re.sub(r"^\d+-", "", path.stem)
    return Step(id=sid, path=path, title=meta.get("title", sid), section=meta.get("section", ""),
                default=meta.get("default", "on"), check_as=meta.get("check-as", "user"),
                when=meta.get("when", ""), after=meta.get("after", ""), manual=meta.get("manual", ""),
                capture=capture, apply=lines)


def load(machine):
    d = steps_dir(machine)
    if not d:
        return []
    return [parse(p) for p in sorted(d.glob("[0-9]*-*.sh"))]


# ---------------------------------------------------------------- what's personal, found on this laptop

def lan_subnet():
    rc, out, _ = run(["ip", "-4", "-o", "route", "show", "scope", "link"])
    for line in out.splitlines():
        parts = line.split()
        if parts and re.match(r"(192\.168|10\.|172\.(1[6-9]|2\d|3[01]))\.", parts[0]) and "docker" not in line \
                and "br-" not in line and "veth" not in line:
            return parts[0]
    return ""


def ntfs_partitions():
    """[(uuid, size, disk)] for NTFS partitions."""
    rc, out, _ = run(["lsblk", "-bnro", "UUID,FSTYPE,SIZE,PKNAME"])
    found = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 4 and p[1] in ("ntfs", "ntfs3") and p[2].isdigit():
            found.append((p[0], int(p[2]), p[3]))
    return found


def root_disk():
    rc, out, _ = run(["findmnt", "-no", "SOURCE", "/"])
    src = out.strip().split("[")[0]
    rc, out, _ = run(["lsblk", "-no", "PKNAME", src])
    return out.strip().splitlines()[0] if out.strip() else ""


def values(ctx):
    """Placeholder -> value on this laptop. Saved in local config, never in the repo."""
    cfg = ctx.cfg if ctx.cfg is not None else {}
    parts = ntfs_partitions()
    sysdisk = root_disk()
    data = cfg.get("ntfs_data_uuid")
    if not data or not Path(f"/dev/disk/by-uuid/{data}").exists():
        other = [p for p in parts if p[2] != sysdisk] or parts
        data = max(other, key=lambda p: p[1])[0] if other else ""
        if data:
            cfg["ntfs_data_uuid"] = data
    win = next((p[0] for p in sorted(parts, key=lambda p: -p[1]) if p[2] == sysdisk), "")
    return {"USER": USER, "HOME": str(HOME), "UID": str(os.getuid()), "GID": str(os.getgid()),
            "NTFS_UUID": data, "WINDOWS_UUID": win,
            "LAN_SUBNET": cfg.get("lan_subnet") or lan_subnet()}


def render(text, vals):
    for k, v in vals.items():
        text = text.replace(f"__{k}__", v)
    return text


def scrub(text, vals):
    """Laptop text -> repo text: personal values back to placeholders (longest first)."""
    for k in ("HOME", "NTFS_UUID", "WINDOWS_UUID", "LAN_SUBNET", "USER"):
        v = vals.get(k)
        if v and len(v) > 2:
            text = re.sub(rf"(?<![\w.-]){re.escape(v)}(?![\w-])", f"__{k}__", text)
    return text


def expand(line, step, vals):
    """$R, $HOME, $USER and the placeholders in a command line, filled in before it runs
    (root commands don't have your environment)."""
    env = dict(vals, R=str(STAGE / step.id))
    def sub(m):
        name = m.group(1) or m.group(2)
        return env.get(name, m.group(0))
    line = re.sub(r"\$\{(\w+)\}|\$(R|HOME|USER|UID|GID|NTFS_UUID|WINDOWS_UUID|LAN_SUBNET)\b", sub, line)
    return re.sub(r"(^|\s)~/", lambda m: m.group(1) + str(HOME) + "/", line)


# ---------------------------------------------------------------- running the tests

def _env(step, vals):
    env = dict(os.environ)
    env.update(vals)
    env["R"] = str(STAGE / step.id)
    env["STEP_FILES"] = str(step.files)
    env["TEST_ROOT"] = TEST_ROOT
    return env


def _shell(step, func):
    return f'set +e; source {json.dumps(str(step.path))}; {func}'


def test_user(step, vals, func="check"):
    try:
        p = subprocess.run(["bash", "-c", _shell(step, func)], capture_output=True, text=True,
                           env=_env(step, vals), timeout=60, stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout.strip().splitlines() or [""])[-1]
    except subprocess.TimeoutExpired:
        return 1, "The test took too long."


def test_root_batch(steps, vals, gui):
    """{step id: (rc, last line)} for root tests, all in one request to the administrator session."""
    scripts = {s.id: {"script": _shell(s, "check"), "env": {k: v for k, v in _env(s, vals).items()
                                                            if k in vals or k in ("R", "STEP_FILES", "TEST_ROOT")}}
               for s in steps}
    if not scripts:
        return {}
    if os.geteuid() == 0 or TEST_ROOT:
        return {sid: _run_direct(d) for sid, d in scripts.items()}
    from .root import RootSession
    try:
        rc, lines = RootSession.get(gui).call("probe", scripts=scripts)
        data = json.loads("\n".join(lines))
        return {k: tuple(v) for k, v in data.items()}
    except (PermissionError, RuntimeError, json.JSONDecodeError, ValueError):
        return {}


def _run_direct(d):
    env = dict(os.environ, **d["env"])
    try:
        p = subprocess.run(["bash", "-c", d["script"]], capture_output=True, text=True, env=env, timeout=60,
                           stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout.strip().splitlines() or [""])[-1]
    except subprocess.TimeoutExpired:
        return 1, "The test took too long."


# ---------------------------------------------------------------- captured files

def _dest(path):
    return Path(TEST_ROOT + path) if path.startswith("/") else HOME / path.removeprefix("~/")


def captured_here(step):
    """Files on this laptop that match the step's capture globs: [(abs path str, Path)]."""
    out = []
    for g in step.capture:
        pattern = str(_dest(g)) if not g.startswith("~/") else str(HOME / g[2:])
        for f in sorted(glob.glob(pattern)):
            p = Path(f)
            if p.is_file() and not p.name.endswith((".bak", ".orig", "~")):
                rel = str(p)[len(TEST_ROOT):] if TEST_ROOT and str(p).startswith(TEST_ROOT) else str(p)
                if rel.startswith(str(HOME) + "/"):
                    rel = "~/" + rel[len(str(HOME)) + 1:]
                out.append((rel, p))
    return out


def captured_repo(step):
    """[(abs path str, repo file)] saved earlier."""
    base = step.files / "captured"
    out = []
    if base.is_dir():
        for f in sorted(base.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(base))
                out.append(("~/" + rel[5:] if rel.startswith("home/") else "/" + rel, f))
    return out


def _repo_name(dest):
    return "home/" + dest[2:] if dest.startswith("~/") else dest.lstrip("/")


def capture_changes(step, vals):
    """Files to save into the repo: [(dest, laptop file)] that are new or differ (after scrubbing)."""
    have = {d: f for d, f in captured_repo(step)}
    changed = []
    for dest, p in captured_here(step):
        try:
            text = scrub(p.read_text(), vals)
        except (OSError, UnicodeDecodeError):
            continue
        if dest not in have or have[dest].read_text() != text:
            changed.append((dest, p))
    return changed


def save_captures(step, vals, changes):
    base = step.files / "captured"
    for dest, p in changes:
        out = base / _repo_name(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(scrub(p.read_text(), vals))
    return len(changes)


def restore_lines(step):
    """Commands that put saved files back where they're missing."""
    lines = []
    for dest, f in captured_repo(step):
        if _dest(dest).exists():
            continue
        src = f"$R/captured/{_repo_name(dest)}"
        if dest.startswith("~/"):
            lines.append(f'install -Dm644 "{src}" "{dest.replace("~/", "$HOME/", 1)}"')
        else:
            lines.append(f'sudo install -Dm644 "{src}" "{dest}"')
    return lines


# ---------------------------------------------------------------- staging this step's files

def stage(step, vals):
    """Copy files/<id>/ to the cache with placeholders filled in; returns the folder."""
    out = STAGE / step.id
    if out.exists():
        import shutil
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    if step.files.is_dir():
        for f in step.files.rglob("*"):
            if f.is_file():
                t = out / f.relative_to(step.files)
                t.parent.mkdir(parents=True, exist_ok=True)
                try:
                    t.write_text(render(f.read_text(), vals))
                except UnicodeDecodeError:
                    t.write_bytes(f.read_bytes())
                t.chmod(f.stat().st_mode & 0o777)
    return out
