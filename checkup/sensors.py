"""Temperature, clock speed and power readings from /sys and nvidia-smi."""

import glob
import os
import shutil

from .util import read, run


def cpu_temp():
    best = 0
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(f"{d}/name").strip() in ("coretemp", "k10temp", "zenpower"):
            for f in glob.glob(f"{d}/temp*_input"):
                try:
                    best = max(best, int(read(f).strip() or 0))
                except ValueError:
                    pass
    if best == 0:
        for z in glob.glob("/sys/class/thermal/thermal_zone*"):
            if read(f"{z}/type").strip() == "x86_pkg_temp":
                try:
                    best = int(read(f"{z}/temp").strip())
                except ValueError:
                    pass
    return best // 1000


def cpu_mhz():
    vals = []
    for f in glob.glob("/sys/devices/system/cpu/cpu[0-9]*/cpufreq/scaling_cur_freq"):
        try:
            vals.append(int(read(f).strip()))
        except ValueError:
            pass
    return sum(vals) // len(vals) // 1000 if vals else 0


def has_nvidia():
    if not shutil.which("nvidia-smi"):
        return False
    rc, _, _ = run(["nvidia-smi", "-L"], timeout=10)
    return rc == 0


def gpu_sample(nvidia):
    """(temp °C, clock MHz, power W); None where unknown."""
    if nvidia:
        rc, out, _ = run(["nvidia-smi", "--query-gpu=temperature.gpu,clocks.gr,power.draw",
                          "--format=csv,noheader,nounits"], timeout=10)
        if rc == 0 and out.strip():
            vals = []
            for v in out.splitlines()[0].split(","):
                try:
                    vals.append(float(v.strip()))
                except ValueError:
                    vals.append(None)
            vals += [None] * (3 - len(vals))
            return tuple(vals[:3])
        return (None, None, None)
    for d in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(f"{d}/name").strip() == "amdgpu" and os.path.exists(f"{d}/temp1_input"):
            try:
                return (int(read(f"{d}/temp1_input")) / 1000, None, None)
            except ValueError:
                pass
    return (None, None, None)


def throttle_count():
    v = read("/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count").strip()
    return int(v) if v.isdigit() else None


def on_battery():
    for ps in glob.glob("/sys/class/power_supply/*"):
        if read(f"{ps}/type").strip() == "Mains" and read(f"{ps}/online").strip() == "0":
            return True
    return False
