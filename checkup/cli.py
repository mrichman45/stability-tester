"""Terminal version of Checkup: checkup-cli setup | apply | stability | guide | machine."""

import argparse
import sys

from . import discover, guide, runner
from .root import RootSession
from .checks import CHECKS, FAIL, INFO, OK, SKIP, WARN, Context, run_checks
from .machine import detect, profiles
from .stability import StabilityOptions, StabilityRun

COLORS = {OK: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", SKIP: "\033[90m", INFO: "\033[36m"}
SYMBOL = {OK: "✔", WARN: "⚠", FAIL: "✖", SKIP: "–", INFO: "ℹ"}
RESET = "\033[0m"


def paint(status, text):
    return f"{COLORS.get(status, '')}{text}{RESET}" if sys.stdout.isatty() else text


def pick_machine(cfg):
    m = detect(cfg.get("machine", ""))
    if m.id != "unknown":
        return m
    profs = profiles()
    print("Which laptop is this?")
    ids = list(profs)
    for i, mid in enumerate(ids, 1):
        print(f"  {i}. {profs[mid]['label']}")
    print(f"  {len(ids) + 1}. None of these (general checks only)")
    choice = input("Number: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(ids):
        cfg["machine"] = ids[int(choice) - 1]
        guide.save_config(cfg)
        return detect(cfg["machine"])
    return m


def show(results):
    for c, r in results:
        print(f"  {paint(r.status, SYMBOL[r.status])} {c.title:42} {r.detail}")
        if r.manual:
            print(f"      → {r.manual}")


def record(cfg, machine, results, fixed_by=None):
    added = guide.record(cfg, machine, [(c.id, c.title, r.status, r.detail, c.guide) for c, r in results], fixed_by)
    for t in added:
        print(paint(OK, f"  Added to the guide: {t}"))


def cmd_setup(args, cfg):
    machine = pick_machine(cfg)
    print(f"Checking {machine.label}" + (f" (recognised by {machine.detected_by})" if machine.detected_by else "") + "...\n")
    if machine.id != "unknown":
        found = discover.scan(machine, machine.extras, cfg.get("ignored_findings", {}).get(machine.id, []))
        if found:
            discover.save_findings(machine, found)
            machine.extras = detect(cfg.get("machine", "")).extras if detect(cfg.get("machine", "")).id == machine.id else machine.extras
            print(paint(INFO, f"Found {len(found)} new things on this laptop and added them to its guide and profile:"))
            for f in found:
                print(f"  + {f.text}")
            print("  (remove any with 'checkup-cli review')\n")
        discover.write_guide_section(guide.guide_path(cfg, machine), machine.extras)
    ctx = Context(machine, gui=False, cfg=cfg)
    results = run_checks(ctx, cfg.get("ignored", []))
    show(results)
    record(cfg, machine, results)

    todo = [(c, r) for c, r in results if r.status in (FAIL, WARN) and r.fix]
    if not todo:
        print("\nNothing to fix.")
        return 0
    if args.cmd == "setup" and not args.fix:
        n = len(todo)
        print(f"\n{n} problem{'' if n == 1 else 's'} can be fixed automatically. Run 'checkup-cli apply' to fix them all,"
              " or 'checkup-cli setup --fix' to choose one by one.")
        return 1

    if args.cmd == "setup":   # one by one
        chosen = []
        for c, r in todo:
            print(f"\n{c.title}: {r.fix.summary}")
            for line in r.fix.script:
                print(f"    $ {line}")
            if input("Fix this? [y/N] ").strip().lower() == "y":
                chosen.append((c, r))
    else:
        chosen = [(c, r) for c, r in todo if not c.optional or getattr(args, "optional", False)]
        skipped = len(todo) - len(chosen)
        if skipped:
            print(f"\n{skipped} optional step(s) left out; add --optional to include them.")
    if not chosen:
        return 1

    plan = runner.build_plan(chosen)
    print("\n" + plan.describe())
    for p in plan.previews:
        print("\n" + p)
    if not args.yes and input("\nApply all of this? [y/N] ").strip().lower() != "y":
        return 1
    notes, errors = runner.run_python_steps(plan)
    for n in notes:
        print("  " + n)
    for e in errors:
        print(paint(FAIL, "  " + e))
    if plan.needs_admin:
        print("\nYou'll be asked for your password once.")
    guide.remember_fixes(machine, plan.fixed_by)
    rc = runner.execute(plan, False, on_line=print_step)
    if rc == 0 and plan.after:
        print("\nAfterwards: " + " ".join(plan.after))

    print("\nChecking again...\n")
    results = run_checks(Context(machine, gui=False, cfg=cfg), cfg.get("ignored", []))
    show(results)
    record(cfg, machine, results, plan.fixed_by)
    manual = [(c, r) for c, r in results if r.status in (FAIL, WARN, INFO) and r.manual and not r.fix]
    if manual:
        print("\nStill to do by hand:")
        for c, r in manual:
            print(f"  • {c.title}: {r.manual}")
    return 0


def print_step(line):
    if line.startswith(runner.STEP):
        parts = line[len(runner.STEP):].strip().split(" ", 2)
        print(paint(INFO, f"\n[{parts[0]}] $ {runner.display(parts[2].split(': ', 1)[-1]) if len(parts) > 2 else ''}"))
    else:
        print("  " + line)


def cmd_review(args, cfg):
    machine = pick_machine(cfg)
    entries = discover.items(machine.extras)
    if not entries:
        print("Nothing has been found on this laptop yet.")
        return 0
    for i, (id, text) in enumerate(entries, 1):
        print(f"  {i:2}. {text}")
    choice = input("Numbers to remove from the guide and profile (e.g. 2 5), or Enter to keep all: ").split()
    gone = [entries[int(c) - 1][0] for c in choice if c.isdigit() and 1 <= int(c) <= len(entries)]
    if gone:
        discover.remove_items(machine, gone)
        ign = cfg.setdefault("ignored_findings", {}).setdefault(machine.id, [])
        ign += [g for g in gone if g not in ign]
        guide.save_config(cfg)
        machine = detect(cfg.get("machine", ""))
        discover.write_guide_section(guide.guide_path(cfg, machine), machine.extras)
        print(f"Removed {len(gone)}.")
    return 0


def cmd_stability(args, cfg):
    # Works on any computer; only logs to the guide when this is one of our profiled laptops.
    machine = detect(cfg.get("machine", ""))
    opts = StabilityOptions.quick() if args.quick else StabilityOptions()
    if args.cpu_minutes is not None:
        opts.cpu_min = args.cpu_minutes
    if args.gpu_minutes is not None:
        opts.gpu_min = args.gpu_minutes
    if args.ram_mb is not None:
        opts.ram_mb = args.ram_mb
    opts.do_cpu, opts.do_gpu = not args.skip_cpu, not args.skip_gpu
    opts.do_ram, opts.do_disk = not args.skip_ram, not args.skip_disk
    opts.do_health = not args.skip_health
    if machine.id != "unknown" and opts.do_health:
        print(f"Recognised {machine.label}: its profile is tested after the stress tests.")

    last = {"t": None}

    def stage(name, left, total):
        if total:
            print(f"\r  {name.upper():6} {left // 60:02d}:{left % 60:02d} left   ", end="", flush=True)
        elif last["t"] != name:
            print(f"\n==> {name}", flush=True)
        last["t"] = name

    def sample(s):
        if s["stage"] in ("cpu", "gpu", "ram"):
            gpu = f" · GPU {s['gpu_temp']:.0f}°C" if s.get("gpu_temp") is not None else ""
            print(f"\r  {s['stage'].upper():6} CPU {s['cpu_temp']}°C {s['cpu_mhz']} MHz{gpu}      ", end="", flush=True)

    def result(r):
        print(f"\r  {paint(r.status, SYMBOL[r.status])} {r.title:12} {r.detail}" + " " * 10)

    run = StabilityRun(opts, gui=False, on_sample=sample, on_stage=stage, on_result=result,
                       on_note=lambda t: None, machine=machine, cfg=cfg)
    try:
        run.run()
    except KeyboardInterrupt:
        run.cancel()
    overall = run.overall()
    print(f"\nOverall: {paint(overall, {OK: 'stable', WARN: 'stable, with warnings', FAIL: 'problems found'}[overall])}")
    print(f"Report: {run.report_path}")
    reapply = run.needs_reapply()
    if reapply:
        print(f"\n{len(reapply)} fixes from the guide need reapplying:")
        plan = runner.build_plan(reapply)
        print(plan.describe())
        if input("\nReapply them now? [y/N] ").strip().lower() == "y":
            notes, errors = runner.run_python_steps(plan)
            for e in errors:
                print(paint(FAIL, "  " + e))
            runner.execute(plan, False, on_line=print_step)
            guide.remember_fixes(machine, plan.fixed_by)
    added = []
    if machine.id != "unknown":
        added = guide.record(cfg, machine, [(f"stability-{r.id}", f"Stability: {r.title}", r.status, r.detail, "")
                                            for r in run.results])
    for t in added:
        print(paint(OK, f"Added to the guide: {t}"))
    return 0 if overall != FAIL else 1


def cmd_guide(args, cfg):
    path = guide.guide_path(cfg, detect(cfg.get("machine", "")))
    print(f"Guide: {path}")
    if args.sync:
        lines = guide.sync_script(path)
        if not lines:
            print("The guide isn't inside a git repository, so there's nothing to sync.")
            return 1
        return runner.execute(runner.Plan(items=[], script=lines), False, on_line=print_step)
    return 0


def cmd_machine(args, cfg):
    if args.set:
        if args.set not in profiles() and args.set != "auto":
            print("Unknown laptop. Choose from: " + ", ".join(profiles()) + ", auto")
            return 1
        cfg["machine"] = "" if args.set == "auto" else args.set
        guide.save_config(cfg)
    m = detect(cfg.get("machine", ""))
    print(f"{m.label}  [{m.id}]" + (f"  recognised by {m.detected_by}" if m.detected_by else ""))
    print(f"CPU: {m.cpu}\nModel: {m.product}\nChecks: {', '.join(m.checks)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="checkup-cli", description="Checks, one-button setup and stability tests from the laptop guides.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="check this laptop against the guide")
    s.add_argument("--fix", action="store_true", help="choose fixes one by one")
    s.add_argument("--yes", action="store_true")
    a = sub.add_parser("apply", help="set up this laptop: apply every fix from the guide in one go")
    a.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    a.add_argument("--optional", action="store_true", help="also do the optional guide steps")
    st = sub.add_parser("stability", help="stress-test CPU, GPU, RAM and disks")
    st.add_argument("--quick", action="store_true")
    st.add_argument("--cpu-minutes", type=int)
    st.add_argument("--gpu-minutes", type=int)
    st.add_argument("--ram-mb", type=int)
    for t in ("cpu", "gpu", "ram", "disk", "health"):
        st.add_argument(f"--skip-{t}", action="store_true")
    g = sub.add_parser("guide", help="show where the guide is, or sync it with GitHub")
    g.add_argument("--sync", action="store_true")
    sub.add_parser("review", help="review what the scan added to this laptop's guide and profile")
    m = sub.add_parser("machine", help="show or set which laptop this is")
    m.add_argument("--set", metavar="ID", help="laptop id from machines.json, or 'auto'")
    args = ap.parse_args(argv)
    cfg = guide.load_config()
    if args.cmd in ("setup", "apply"):
        try:
            return cmd_setup(args, cfg)
        finally:
            RootSession.get(False).close()
    try:
        return {"stability": cmd_stability, "guide": cmd_guide, "machine": cmd_machine,
                "review": cmd_review}[args.cmd](args, cfg)
    finally:
        RootSession.get(False).close()


if __name__ == "__main__":
    sys.exit(main())
