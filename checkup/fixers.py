"""Pure text transformations used by fixes, kept separate so they can be tested."""

import re

FISH_BEGIN = "# >>> checkup: fastfetch greeting >>>"
FISH_END = "# <<< checkup: fastfetch greeting <<<"
FISH_BLOCK = f"""{FISH_BEGIN}
function fish_greeting
    fastfetch --logo cachyos
end
{FISH_END}
"""

_OPENERS = re.compile(r"^(function|if|for|while|switch|begin)\b")


def _strip_comment(line):
    return line.split("#", 1)[0].strip()


def fish_fastfetch_problems(text):
    """Describe what's wrong with the fastfetch setup in a fish config (empty list = fine)."""
    problems = []
    code = [_strip_comment(l) for l in text.splitlines()]
    calls = [l for l in code if re.search(r"(^|[;\s])fastfetch(\s|;|$)", l)
             and not re.search(r"(command|type|which)\s+(-v\s+)?fastfetch", l)]
    if not calls:
        problems.append("fastfetch isn't set to run when a terminal opens")
    elif len(calls) > 1:
        problems.append(f"fastfetch is set to run {len(calls)} times, so it shows more than once")
    if any(l.startswith("if [") or l == "fi" for l in code):
        problems.append("the config contains bash syntax (if [ ... ] / fi) that fish can't run")
    if any("ALACRITTY_WINDOW_ID" in l for l in code):
        problems.append("fastfetch only runs in Alacritty, not in every terminal")
    if calls and not any("--logo cachyos" in l for l in calls):
        problems.append("fastfetch isn't using the CachyOS logo")
    return problems


def fish_fastfetch_fix(text):
    """Remove every earlier fastfetch/greeting attempt and add one correct greeting block."""
    lines = text.splitlines()
    out, i = [], 0
    while i < len(lines):
        raw = lines[i]
        code = _strip_comment(raw)

        # Earlier checkup block
        if raw.strip() == FISH_BEGIN:
            while i < len(lines) and lines[i].strip() != FISH_END:
                i += 1
            i += 1
            continue

        # Any fish_greeting function, or a fish if-block mentioning Alacritty/fastfetch
        starts_block = code.startswith("function fish_greeting") or (
            code.startswith("if ") and not code.startswith("if [")
            and ("ALACRITTY_WINDOW_ID" in code or "fastfetch" in code) and not code.endswith("end"))
        if starts_block:
            depth = 0
            while i < len(lines):
                c = _strip_comment(lines[i])
                if _OPENERS.match(c) and not re.search(r";\s*end$", c):
                    depth += 1
                if c == "end":
                    depth -= 1
                i += 1
                if depth <= 0:
                    break
            continue

        # Bash-style block that was pasted by mistake
        if code.startswith("if [") and ("ALACRITTY" in code or "fastfetch" in code or i + 1 < len(lines) and "fastfetch" in lines[i + 1]):
            while i < len(lines) and _strip_comment(lines[i]) != "fi":
                i += 1
            i += 1
            continue

        # One-liners: `if set -q ALACRITTY_WINDOW_ID; fastfetch; end` or a bare `fastfetch`
        if re.search(r"(^|[;\s])fastfetch(\s|;|$)", code) and (code.startswith("fastfetch") or code.startswith("if ")):
            i += 1
            continue

        out.append(raw)
        i += 1

    while out and not out[-1].strip():
        out.pop()
    body = "\n".join(out)
    return (body + "\n\n" if body else "") + FISH_BLOCK


def fstab_ntfs_line(uuid, mountpoint, uid, gid):
    return (f"UUID={uuid}  {mountpoint}  ntfs3  "
            f"defaults,uid={uid},gid={gid},umask=022,nofail,x-gvfs-show  0 0")


def fstab_entries(text, uuid):
    return [l for l in text.splitlines()
            if not l.lstrip().startswith("#") and re.search(rf"\bUUID={re.escape(uuid)}\b", l, re.I)]


def fstab_problems(text, uuid):
    entries = fstab_entries(text, uuid)
    if not entries:
        return ["the drive isn't in /etc/fstab, so it won't mount at boot"]
    problems = []
    if len(entries) > 1:
        problems.append(f"the drive is listed {len(entries)} times in /etc/fstab")
    for e in entries:
        fields = e.split()
        opts = fields[3] if len(fields) > 3 else ""
        if "nofail" not in opts.split(","):
            problems.append("the fstab line is missing 'nofail' (the laptop could hang at boot if the drive fails)")
        if "force" in opts.split(","):
            problems.append("the fstab line uses 'force', which can damage a dirty NTFS drive")
        if len(fields) > 2 and fields[2] not in ("ntfs3", "ntfs", "ntfs-3g"):
            problems.append(f"the fstab line uses filesystem type '{fields[2]}' instead of ntfs3")
    return list(dict.fromkeys(problems))


def fstab_fix(text, uuid, mountpoint, uid, gid):
    """Replace every line for this drive with one correct line."""
    keep = [l for l in text.splitlines()
            if l.lstrip().startswith("#") or not re.search(rf"\bUUID={re.escape(uuid)}\b", l, re.I)]
    while keep and not keep[-1].strip():
        keep.pop()
    return "\n".join(keep) + "\n" + fstab_ntfs_line(uuid, mountpoint, uid, gid) + "\n"
