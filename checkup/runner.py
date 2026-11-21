"""Turn chosen fixes into one plan and run it: file edits first, then one visible shell script."""

import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from .util import HOME, shell_quote

WORKDIR = HOME / ".cache/checkup"


@dataclass
class Plan:
    items: list                                     # [(Check, Result)] being fixed
    python_steps: list = field(default_factory=list)  # [(title, callable)]
    script: list = field(default_factory=list)
    after: list = field(default_factory=list)
    dangers: list = field(default_factory=list)
    previews: list = field(default_factory=list)

    @property
    def fixed_by(self):
        return {c.id: r.fix.summary for c, r in self.items}

    def describe(self):
        """Human-readable summary for the confirmation dialog / terminal prompt."""
        parts = ["Fixes:"] + [f"  • {c.title}: {r.fix.summary}" for c, r in self.items]
        if self.python_steps:
            parts += ["", "Files Checkup edits for you (backed up first):"] + [f"  • {t}" for t, _ in self.python_steps]
        if self.script:
            parts += ["", "Commands (run in a terminal window you can watch):"] + [f"  $ {l}" for l in self.script]
        if self.dangers:
            parts += ["", "Please read:"] + [f"  ! {d}" for d in self.dangers]
        if self.after:
            parts += ["", "Afterwards:"] + [f"  • {a}" for a in self.after]
        return "\n".join(parts)


_SYU = re.compile(r"^sudo pacman -Syu\b(.*)$")
_INSTALL = re.compile(r"^sudo pacman -S --needed (.+)$")


def _merge_pacman(lines):
    """One system update + one install instead of many pacman runs (fewer prompts, right order)."""
    syu, pkgs, rest = False, [], []
    for line in lines:
        m = _SYU.match(line)
        if m:
            syu = True
            pkgs += [a for a in m.group(1).split() if a != "--needed"]
            continue
        m = _INSTALL.match(line)
        if m:
            pkgs += m.group(1).split()
            continue
        rest.append(line)
    pkgs = list(dict.fromkeys(pkgs))
    # If the same package is requested from a specific repo, drop the plain request.
    named = {p.split("/", 1)[1] for p in pkgs if "/" in p}
    pkgs = [p for p in pkgs if "/" in p or p not in named]
    head = []
    if syu:
        head = ["sudo pacman -Syu" + (" --needed " + " ".join(pkgs) if pkgs else "")]
    elif pkgs:
        head = ["sudo pacman -S --needed " + " ".join(pkgs)]
    return head + list(dict.fromkeys(rest))


def build_plan(selected):
    plan = Plan(items=[(c, r) for c, r in selected if r.fix])
    lines = []
    for c, r in plan.items:
        f = r.fix
        if f.python:
            plan.python_steps.append((f"{c.title}: {f.summary}", f.python))
        lines += f.script
        if f.after and f.after not in plan.after:
            plan.after.append(f.after)
        if f.danger:
            plan.dangers.append(f"{c.title}: {f.danger}")
        if f.preview:
            plan.previews.append(f.preview)
    plan.script = _merge_pacman(lines)
    return plan


def run_python_steps(plan):
    """Returns (notes, errors)."""
    notes, errors = [], []
    for title, fn in plan.python_steps:
        try:
            notes.append(fn() or title)
        except Exception as e:
            errors.append(f"{title}: {e}")
    return notes, errors


def write_script(plan, title):
    WORKDIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = WORKDIR / f"fix-{stamp}.sh"
    status = WORKDIR / f"fix-{stamp}.status"
    after = "".join(f"echo '  • {a.replace(chr(39), '')}'\n" for a in plan.after)
    body = [
        "#!/usr/bin/env bash",
        f"status_file={shell_quote(status)}",
        "pause() { [ -n \"${CHECKUP_NO_PAUSE:-}\" ] || read -rp 'Press Enter to close this window...'; }",
        "trap 'echo 1 > \"$status_file\"; printf \"\\n\\e[31mA step failed, so the steps after it were not run.\\e[0m\\n\"; pause; exit 1' ERR",
        "set -eE",
        f"printf '\\e[1;36m== Checkup: %s ==\\e[0m\\n' {shell_quote(title)}",
    ]
    for line in plan.script:
        body.append(f"printf '\\n\\e[1m$ %s\\e[0m\\n' {shell_quote(line)}")
        body.append(line)
    body += [
        "echo 0 > \"$status_file\"",
        "printf '\\n\\e[32mAll done.\\e[0m\\n'",
    ]
    if plan.after:
        body += ["echo", "echo 'Afterwards:'", after.rstrip("\n")]
    body.append("pause")
    path.write_text("\n".join(body) + "\n")
    path.chmod(0o755)
    return path, status


def terminal_command(script):
    s = str(script)
    for name, cmd in (("alacritty", ["alacritty", "-e", "bash", s]),
                      ("konsole", ["konsole", "-e", "bash", s]),
                      ("kitty", ["kitty", "bash", s]),
                      ("foot", ["foot", "bash", s]),
                      ("gnome-terminal", ["gnome-terminal", "--wait", "--", "bash", s]),
                      ("xterm", ["xterm", "-e", "bash", s])):
        if shutil.which(name):
            return cmd
    return None


def read_status(status_path):
    try:
        return int(status_path.read_text().strip())
    except (OSError, ValueError):
        return None   # window closed before finishing


def run_script_here(script):
    """Terminal version: run inline (sudo prompts appear right here)."""
    env = dict(os.environ, CHECKUP_NO_PAUSE="1")
    return subprocess.call(["bash", str(script)], env=env)
