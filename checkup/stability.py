"""Stability tests (CPU, GPU, RAM, disks, kernel log) with live sensor samples."""

import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import sensors
from .checks import FAIL, OK, SKIP, WARN
from .util import HOME, root_command, which


@dataclass
class StabilityOptions:
    cpu_min: int = 15
    gpu_min: int = 10
    ram_mb: int = 0          # 0 = automatic
    do_cpu: bool = True
    do_gpu: bool = True
    do_ram: bool = True
    do_disk: bool = True
    do_health: bool = True   # laptop health tests, only on a recognised laptop

    @classmethod
    def quick(cls):
        return cls(cpu_min=5, gpu_min=3, ram_mb=1024)


@dataclass
class TestResult:
    id: str
    title: str
    status: str
    detail: str


@dataclass
class Samples:
    rows: list = field(default_factory=list)   # dicts: t, stage, cpu_temp, cpu_mhz, gpu_temp, gpu_mhz, gpu_w

    def of(self, stage, key):
        return [r[key] for r in self.rows if r["stage"] == stage and r.get(key) is not None]


def _max(vals, default=0):
    return max(vals) if vals else default


def _avg(vals, default=0):
    return sum(vals) / len(vals) if vals else default


class StabilityRun:
    """Call run() from a worker thread. Callbacks are called from worker threads too."""

    def __init__(self, opts, gui=False, on_sample=None, on_stage=None, on_result=None, on_note=None, machine=None, cfg=None):
        self.opts = opts
        self.cfg = cfg
        # The stress tests work on any computer. A recognised laptop adds its own
        # temperature limits and health tests (machines.json).
        self.machine = machine if machine and machine.id != "unknown" else None
        limits = self.machine.limits if self.machine else {}
        self.cpu_limit = limits.get("cpu", 100)
        self.gpu_limit = limits.get("gpu", 90)
        self.health = []   # [(Check, Result)] from the laptop health tests
        self.gui = gui
        self.on_sample = on_sample or (lambda s: None)
        self.on_stage = on_stage or (lambda stage, left, total: None)
        self.on_result = on_result or (lambda r: None)
        self.on_note = on_note or (lambda text: None)
        self.samples = Samples()
        self.results = []
        self.notes = []
        self.stage = "idle"
        self._cancel = threading.Event()
        self._proc = None
        self._nvidia = sensors.has_nvidia()
        self._sampling = False
        self.report_path = None

    # ---------- plumbing ----------
    def cancel(self):
        self._cancel.set()
        p = self._proc
        if p and p.poll() is None:
            try:
                p.terminate()
            except OSError:
                pass

    def _note(self, text):
        self.notes.append(text)
        self.on_note(text)

    def _result(self, id, title, status, detail):
        r = TestResult(id, title, status, detail)
        self.results.append(r)
        self.on_result(r)

    def _sampler(self):
        while self._sampling:
            gpu = sensors.gpu_sample(self._nvidia) if self.stage == "gpu" else (None, None, None)
            row = {"t": time.time(), "stage": self.stage, "cpu_temp": sensors.cpu_temp(),
                   "cpu_mhz": sensors.cpu_mhz(), "gpu_temp": gpu[0], "gpu_mhz": gpu[1], "gpu_w": gpu[2]}
            self.samples.rows.append(row)
            self.on_sample(row)
            time.sleep(2)

    def _wait(self, proc, seconds):
        """Wait for proc or the time limit. Returns proc's exit code, or None if we stopped it at the limit."""
        start = time.time()
        while True:
            rc = proc.poll()
            if rc is not None:
                return rc
            left = seconds - (time.time() - start)
            self.on_stage(self.stage, max(0, int(left)), seconds)
            if self._cancel.is_set():
                proc.terminate()
                proc.wait()
                return None
            if left <= 0:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                return None
            time.sleep(1)

    # ---------- tests ----------
    def _cpu(self, workdir):
        self.stage = "cpu"
        if not which("stress-ng"):
            return self._result("cpu", "CPU", SKIP, "stress-ng isn't installed.")
        before = sensors.throttle_count()
        log = workdir / "cpu.log"
        with open(log, "w") as f:
            self._proc = subprocess.Popen(
                ["stress-ng", "--cpu", "0", "--cpu-method", "all", "--verify",
                 "--timeout", f"{self.opts.cpu_min}m", "--metrics-brief"], stdout=f, stderr=subprocess.STDOUT)
            rc = self._wait(self._proc, self.opts.cpu_min * 60 + 30)
        if self._cancel.is_set():
            return
        after = sensors.throttle_count()
        text = log.read_text(errors="replace")
        temps, mhz = self.samples.of("cpu", "cpu_temp"), self.samples.of("cpu", "cpu_mhz")
        tmax, favg = _max(temps), _avg(mhz[2:] or mhz)
        throttles = (after - before) if before is not None and after is not None else None
        self._note(f"CPU: max {tmax}°C, average {favg:.0f} MHz"
                   + (f", {throttles} throttling events" if throttles is not None else ""))
        if (rc not in (0, None)) or re.search(r"failed: [1-9]", text):
            self._note("stress-ng errors:\n" + "\n".join(l for l in text.splitlines() if "fail" in l.lower() and "failed: 0" not in l)[:2000])
            self._result("cpu", "CPU", FAIL, "Calculation errors or a crash under load. Check undervolt/overclock settings and cooling.")
        elif tmax >= self.cpu_limit:
            self._result("cpu", "CPU", WARN, f"Stable, but reached {tmax}°C (limit for this computer: {self.cpu_limit}°C). Clean the vents, use a cooling pad, or a lower performance mode.")
        elif throttles:
            self._result("cpu", "CPU", OK, f"Stable, max {tmax}°C. Throttled briefly: normal for laptops at full load.")
        else:
            self._result("cpu", "CPU", OK, f"Stable, max {tmax}°C, average {favg:.0f} MHz.")

    def _gpu(self, workdir):
        self.stage = "gpu"
        if not which("glmark2"):
            return self._result("gpu", "GPU", SKIP, "glmark2 isn't installed.")
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return self._result("gpu", "GPU", SKIP, "Needs to run from the desktop.")
        env = dict(os.environ)
        if self._nvidia:  # run on the NVIDIA card on laptops with switchable graphics
            env.update(__NV_PRIME_RENDER_OFFLOAD="1", __GLX_VENDOR_LIBRARY_NAME="nvidia",
                       __VK_LAYER_NV_optimus="NVIDIA_only")
        log = workdir / "gpu.log"
        with open(log, "w") as f:
            self._proc = subprocess.Popen(["glmark2", "--off-screen", "--run-forever", "-s", "1920x1080"],
                                          stdout=f, stderr=subprocess.STDOUT, env=env)
            rc = self._wait(self._proc, self.opts.gpu_min * 60)
        if self._cancel.is_set():
            return
        text = log.read_text(errors="replace")
        m = re.search(r"GL_RENDERER:\s*(.+)", text)
        renderer = m.group(1).strip() if m else "GPU"
        temps = self.samples.of("gpu", "gpu_temp")
        gmax, gclk, gpow = _max(temps), _avg(self.samples.of("gpu", "gpu_mhz")), _max(self.samples.of("gpu", "gpu_w"))
        self._note(f"GPU ({renderer}): max {gmax:.0f}°C, average {gclk:.0f} MHz, peak {gpow:.0f} W. "
                   "glmark2 is a moderate load; for a full torture test also run Unigine Superposition or a demanding game.")
        if rc not in (None, 0):
            self._note("glmark2 output:\n" + text[-1500:])
            self._result("gpu", "GPU", FAIL, f"The test program crashed (exit {rc}).")
        elif gmax >= self.gpu_limit:
            self._result("gpu", "GPU", WARN, f"Stable, but reached {gmax:.0f}°C (limit for this computer: {self.gpu_limit}°C). Check vents and fans.")
        else:
            self._result("gpu", "GPU", OK, f"Stable on {renderer}" + (f", max {gmax:.0f}°C." if temps else "."))

    def _root_part(self, start_epoch):
        ram = 0
        if self.opts.do_ram:
            if not which("memtester"):
                self._result("ram", "RAM", SKIP, "memtester isn't installed.")
            else:
                ram = self.opts.ram_mb
                if not ram:
                    avail = 0
                    for line in Path("/proc/meminfo").read_text().splitlines():
                        if line.startswith("MemAvailable:"):
                            avail = int(line.split()[1]) // 1024
                    ram = min(avail // 4, 4096)
        smart = 1 if (self.opts.do_disk and which("smartctl")) else 0
        if self.opts.do_disk and not smart:
            self._result("disk", "Disks", SKIP, "smartctl isn't installed.")

        self.stage = "admin"
        self.on_stage("admin", 0, 0)
        cmd = root_command(["stability", "--ram", str(ram), "--smart", str(smart), "--since", str(int(start_epoch))], self.gui)
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        ram_rc, ram_lines, klog, got_any = None, [], [], False
        ram_start = None
        for line in self._proc.stdout:
            line = line.rstrip("\n")
            if self._cancel.is_set():
                break
            got_any = got_any or line.startswith(("STAGE", "DONE"))
            if line.startswith("STAGE "):
                self.stage = line.split()[1]
                if self.stage == "ram":
                    ram_start = time.time()
                self.on_stage(self.stage, 0, 0)
            elif line.startswith("MEMTESTER "):
                ram_lines.append(line[10:])
                est = max(60, ram // 4)
                if ram_start:
                    self.on_stage("ram", max(0, int(est - (time.time() - ram_start))), est)
            elif line.startswith("RAM_RC "):
                ram_rc = int(line.split()[1])
            elif line.startswith("SMART "):
                self._disk(json.loads(line[6:]))
            elif line.startswith("KLOG "):
                klog.append(line[5:])
        rc = self._proc.wait()
        if self._cancel.is_set():
            self._note("Stopped. A RAM test that already started may keep running in the background for a few minutes.")
            return
        if not got_any:
            reason = "Administrator access was refused or cancelled." if rc in (126, 127, 1) else f"Helper failed (exit {rc})."
            for id, title, wanted in (("ram", "RAM", ram), ("disk", "Disks", smart)):
                if wanted:
                    self._result(id, title, SKIP, reason)
            self._result("log", "System log", SKIP, reason)
            return

        if ram:
            self._note(f"RAM: tested {ram} MB. For a complete test, boot MemTest86+ from a USB stick overnight.")
            if ram_rc in (None, 127):
                self._result("ram", "RAM", SKIP, "memtester couldn't be started.")
            elif ram_rc == 0:
                self._result("ram", "RAM", OK, f"No errors in {ram} MB.")
            else:
                self._note("memtester output:\n" + "\n".join(ram_lines[-20:]))
                self._result("ram", "RAM", FAIL, "Memory errors found. Confirm with MemTest86+, and reset any RAM overclock/XMP.")

        if klog:
            self._note("Kernel messages:\n" + "\n".join(klog[:20]))
            self._result("log", "System log", WARN, f"{len(klog)} hardware-related errors logged during the test (see the report).")
        else:
            self._result("log", "System log", OK, "No hardware errors logged.")

    def _health(self):
        from .checks import Context
        from .health import run_health
        self.stage = "health"
        self.on_stage("health", 0, 0)
        self.health = run_health(Context(self.machine, gui=self.gui, cfg=self.cfg), self.machine.health,
                                 profile_checks=self.machine.checks)
        for c, r in self.health:
            self._result(f"health:{c.id}", c.title, r.status, r.detail + (f" → {r.manual}" if r.manual else ""))

    def needs_reapply(self):
        """Health results that failed and come with a fix to reapply."""
        return [(c, r) for c, r in self.health if r.status in (FAIL, WARN) and r.fix]

    def _disk(self, item):
        d, data = item["disk"], item["data"]
        model = data.get("model_name", "")
        title = f"Disk {d}"
        health = data.get("nvme_smart_health_information_log", {})
        used, media = health.get("percentage_used"), health.get("media_errors")
        passed = data.get("smart_status", {}).get("passed")
        self._note(f"/dev/{d} {model}: wear used {used if used is not None else 'n/a'}%, media errors {media if media is not None else 'n/a'}")
        if passed is False:
            self._result(f"disk:{d}", title, FAIL, "The drive reports it is failing. Back up now.")
        elif media:
            self._result(f"disk:{d}", title, WARN, f"{media} media errors recorded. Keep backups current.")
        elif passed:
            self._result(f"disk:{d}", title, OK, "Healthy" + (f", {used}% of rated life used." if used is not None else "."))
        else:
            self._result(f"disk:{d}", title, SKIP, "Health data not available.")

    # ---------- main ----------
    def run(self):
        start = time.time()
        workdir = HOME / ".cache/checkup/stability"
        workdir.mkdir(parents=True, exist_ok=True)
        if sensors.on_battery():
            self._note("Running on battery: plug in for a meaningful result.")
        self._sampling = True
        threading.Thread(target=self._sampler, daemon=True).start()
        try:
            if self.opts.do_cpu and not self._cancel.is_set():
                self._cpu(workdir)
            if self.opts.do_gpu and not self._cancel.is_set():
                self._gpu(workdir)
            if not self._cancel.is_set():
                self._root_part(start)
            if self.machine and self.opts.do_health and not self._cancel.is_set():
                self._health()
        finally:
            self._sampling = False
            self.stage = "done"
        self.report_path = self._write_report()
        return self.results

    def overall(self):
        statuses = {r.status for r in self.results}
        return FAIL if FAIL in statuses else WARN if WARN in statuses else OK

    def _write_report(self):
        path = HOME / f"stability-report-{time.strftime('%Y%m%d-%H%M')}.txt"
        lines = [f"Checkup stability report - {time.ctime()}", "", "SUMMARY"]
        lines += [f"  {r.status.upper():5} {r.title:12} {r.detail}" for r in self.results]
        lines += ["", f"OVERALL: {self.overall().upper()}" + (" (stopped early)" if self._cancel.is_set() else ""),
                  "", "DETAILS"] + self.notes
        path.write_text("\n".join(lines) + "\n")
        return path
