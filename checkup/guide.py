"""Settings, remembered results, and automatic entries in GUIDE.md."""

import json
import re
import shutil
import time
from pathlib import Path

from .util import HOME, repo_dir, shell_quote

CONFIG_FILE = HOME / ".config/checkup/config.json"
STATE_FILE = HOME / ".local/state/checkup/state.json"
MARKER = "<!-- checkup:fix-log -->"
PACKAGED_DIR = Path("/usr/share/checkup")
REPO_DIR = Path(__file__).resolve().parent.parent

# Results that change by themselves (Wi-Fi, camera switch, reboots) aren't "fixes".
NOT_LOGGED = {"dns", "camera", "reboot"}
GOOD = {"ok", "info"}
BAD = {"fail", "warn"}


def _load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def load_config():
    cfg = {"guide_path": "", "ignored": [], "machine": ""}
    cfg.update(_load(CONFIG_FILE, {}))
    return cfg


def save_config(cfg):
    _save(CONFIG_FILE, cfg)


def guide_path(cfg, machine):
    """This laptop's guide: your setting, else the GitHub clone (~/.local/src/stability-tester), else a local copy."""
    rel = getattr(machine, "guide", "") or "guides/README.md"
    custom = (cfg.get("guide_paths") or {}).get(machine.id)
    if custom and Path(custom).exists():
        return Path(custom)
    clone = repo_dir()
    if (clone / rel).exists() and (clone / ".git").exists():
        return clone / rel
    local = HOME / ".local/share/checkup" / rel
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        for base in (PACKAGED_DIR, REPO_DIR):
            if (base / rel).exists():
                shutil.copy(base / rel, local)
                break
        else:
            local.write_text(f"# {getattr(machine, 'label', 'Guide')}\n\n## Fix log\n\n{MARKER}\n")
    return local


def headings(path):
    """{anchor: heading title} so the app can jump to a guide section."""
    result, pending = {}, None
    for line in Path(path).read_text(errors="replace").splitlines():
        m = re.match(r'<a id="([^"]+)"></a>', line.strip())
        if m:
            pending = m.group(1)
            continue
        m = re.match(r"#{2,4}\s+(.+)", line)
        if m:
            title = m.group(1).strip()
            slug = re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-")
            result.setdefault(slug, title)
            if pending:
                result[pending] = title
            pending = None
        elif line.strip():
            pending = None
    return result


def add_entries(path, entries):
    """Insert entries (markdown strings) right after the fix-log marker, newest first."""
    if not entries:
        return
    text = Path(path).read_text(errors="replace")
    block = "\n".join(entries) + "\n"
    if MARKER in text:
        text = text.replace(MARKER, MARKER + "\n\n" + block, 1)
    else:
        text = text.rstrip() + f"\n\n## Fix log\n\n{MARKER}\n\n{block}"
    Path(path).write_text(text)


def remember_fixes(machine, fixed_by):
    """Remember which fixes Checkup applied, so the guide entry can say how it was fixed later."""
    if not fixed_by:
        return
    state = _load(STATE_FILE, {})
    state.setdefault(machine.id, {}).setdefault("_pending", {}).update(fixed_by)
    _save(STATE_FILE, state)


def record(cfg, machine, items, fixed_by=None):
    """Remember this run's results; add a guide entry for everything that went from bad to good.

    items: [(id, title, status, detail, guide_anchor)]
    fixed_by: {id: summary of the fix Checkup applied}
    Returns the titles that were added to the guide.
    """
    state = _load(STATE_FILE, {})
    mstate = state.setdefault(machine.id, {})
    pending = mstate.setdefault("_pending", {})
    pending.update(fixed_by or {})
    entries, added = [], []
    now = time.strftime("%Y-%m-%d")
    for id, title, status, detail, anchor in items:
        prev = mstate.get(id)
        if prev and prev["status"] in BAD and status in GOOD and id not in NOT_LOGGED:
            key = id if id in pending else id.split(":")[-1]
            how = pending.pop(key, "Fixed outside Checkup")
            entry = (f"### {now} · {machine.label} · {title}\n"
                     f"- **Problem:** {prev['detail']}\n"
                     f"- **Fix:** {how}\n"
                     + (f"- **More:** [{title}](#{anchor})\n" if anchor else ""))
            entries.append(entry)
            added.append(title)
        if status != "skip":
            mstate[id] = {"status": status, "detail": detail, "when": now}
    _save(STATE_FILE, state)
    add_entries(guide_path(cfg, machine), entries)
    return added


def sync_script(path):
    """Commands that commit the guide (and the laptop profiles) and push them to GitHub,
    or None if the guide isn't in a git clone."""
    repo = Path(path).resolve().parent
    while repo != repo.parent and not (repo / ".git").exists():
        repo = repo.parent
    if not (repo / ".git").exists():
        return None
    r = shell_quote(repo)
    files = [shell_quote(Path(path).resolve())] + ([shell_quote(repo / "machines.json")] if (repo / "machines.json").exists() else [])
    return [f"cd {r} && git add {' '.join(files)}",
            f"cd {r} && (git diff --cached --quiet || git commit -m \"Guides: updates recorded by Checkup on $(hostname)\")",
            f"cd {r} && GIT_TERMINAL_PROMPT=0 git pull --rebase",
            f"cd {r} && GIT_TERMINAL_PROMPT=0 git push"]
