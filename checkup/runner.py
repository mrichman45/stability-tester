"""Turn chosen fixes into one plan and run it: file edits first, then the commands, in order.

Commands that need administrator rights go through the one administrator session (root.py),
so the password is asked at most once. Plans with only user-level commands need no password.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field

from .root import RootSession

STEP = "\x1eSTEP"


@dataclass
class Plan:
    items: list                                       # [(Check, Result)] being fixed
    python_steps: list = field(default_factory=list)  # [(title, callable)]
    script: list = field(default_factory=list)        # command lines (see steps())
    after: list = field(default_factory=list)
    dangers: list = field(default_factory=list)
    previews: list = field(default_factory=list)

    @property
    def fixed_by(self):
        return {c.id: r.fix.summary for c, r in self.items}

    @property
    def needs_admin(self):
        return any(k in ("root", "build", "aur") for k, _ in steps(self.script))

    def describe(self):
        parts = ["Fixes:"] + [f"  • {c.title}: {r.fix.summary}" for c, r in self.items]
        if self.python_steps:
            parts += ["", "Files Checkup edits for you (backed up first):"] + [f"  • {t}" for t, _ in self.python_steps]
        if self.script:
            parts += ["", "Commands, in order:"] + [f"  $ {display(l)}" for l in self.script]
        if self.dangers:
            parts += ["", "Please read:"] + [f"  ! {d}" for d in self.dangers]
        if self.after:
            parts += ["", "Afterwards:"] + [f"  • {a}" for a in self.after]
        return "\n".join(parts)


def display(line):
    if line.startswith("@build "):
        return f"build and install the package in {line[7:]}"
    if line.startswith("@aur "):
        return f"build and install {line[5:]} from the AUR"
    return line


def steps(lines):
    """Command lines -> [(kind, value)]. 'sudo X' runs X as root; '@build DIR' and '@aur PKG'
    build as you and install as root; everything else runs as you."""
    out = []
    for line in lines:
        if line.startswith("sudo "):
            out.append(("root", line[5:]))
        elif line.startswith("@build "):
            out.append(("build", line[7:].strip()))
        elif line.startswith("@aur "):
            out.append(("aur", line[5:].strip()))
        else:
            out.append(("user", line))
    return out


_SYU = re.compile(r"^sudo pacman -Syu\b(.*)$")
_INSTALL = re.compile(r"^sudo pacman -S --needed (.+)$")


def _merge_pacman(lines):
    """One system update + one install instead of many pacman runs, placed first."""
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


def execute(plan, gui, on_line=print):
    """Run the plan's commands, streaming output to on_line. Returns the exit code."""
    if not plan.script:
        return 0
    if not plan.needs_admin:   # nothing needs a password: run here, as you
        total = len(plan.script)
        for n, line in enumerate(plan.script, 1):
            on_line(f"{STEP} {n}/{total} user: {line}")
            p = subprocess.Popen(["bash", "-c", line], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 stdin=subprocess.DEVNULL, text=True, cwd=os.path.expanduser("~"), errors="replace")
            for out in p.stdout:
                on_line(out.rstrip("\n"))
            rc = p.wait()
            if rc != 0:
                on_line(f"This step failed (exit {rc}), so the steps after it were not run.")
                return rc
        return 0
    session = RootSession.get(gui)
    payload = [{"kind": k, ("cmd" if k in ("root", "user") else "dir" if k == "build" else "pkg"): v}
               for k, v in steps(plan.script)]
    try:
        for line in session.request("run-plan", steps=payload):
            on_line(line)
    except (PermissionError, RuntimeError) as e:
        on_line(str(e))
        return 126
    return session.last_rc or 0
