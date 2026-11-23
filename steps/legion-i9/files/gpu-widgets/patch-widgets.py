#!/usr/bin/env python3
import os, re, shutil

HELPER = '''

def _nv_asleep():
    """True when the NVIDIA GPU is powered down (runtime-suspended).
    Reading sysfs doesn't wake it; nvidia-smi would, so callers skip NVIDIA then."""
    base = "/sys/bus/pci/devices"
    seen = False
    for d in os.listdir(base):
        p = os.path.join(base, d)
        try:
            with open(p + "/vendor") as f:
                if f.read().strip() != "0x10de":
                    continue
            with open(p + "/class") as f:
                if not f.read().startswith("0x03"):   # display controllers only
                    continue
            seen = True
            with open(p + "/power/runtime_status") as f:
                if f.read().strip() == "active":
                    return False
        except OSError:
            continue
    return seen

'''

def patch(path, transform):
    if not os.path.exists(path):
        print("not installed, skipped:", path); return
    s = open(path).read()
    if "_nv_asleep" in s:
        print("already patched:", path); return
    shutil.copy2(path, path + ".bak")
    new = transform(s)
    open(path, "w").write(new)
    print("patched:", path)

def one(s, old, new):
    assert s.count(old) == 1, "not found once: " + old[:50]
    return s.replace(old, new)

home = os.path.expanduser("~")

def gpu(s):
    s = one(s, 'DRM_CARD_GLOB = "/sys/class/drm/card*"\n',
               'DRM_CARD_GLOB = "/sys/class/drm/card*"\n' + HELPER)
    s = one(s, 'def _nvidia_sample(idx):\n    global _nv_prefix_i\n',
               'def _nvidia_sample(idx):\n    global _nv_prefix_i\n'
               '    if _nv_asleep():\n        return None  # RTX powered down: don\'t wake it\n')
    s = one(s, 'per-process GPU memory source on NVIDIA hosts.\n    """\n',
               'per-process GPU memory source on NVIDIA hosts.\n    """\n'
               '    if _nv_asleep():\n        return []\n')
    if "\nimport os" not in s:
        s = "import os\n" + s
    return s

def sensors(s):
    s = one(s, "import subprocess\n", "import subprocess\nimport os\n" + HELPER)
    s, n = re.subn(r"^(\s*)(p = subprocess\.run\(\['nvidia-smi')",
                   r"\1if _nv_asleep():\n\1    raise OSError('RTX powered down')\n\1\2",
                   s, count=1, flags=re.M)
    assert n == 1, "nvidia-smi call not found in sensors.py"
    return s

patch(home + "/.local/share/nvstats-service/backend/nvstats_gpu.py", gpu)
patch(home + "/.local/share/plasma/plasmoids/org.dfuse.hardwaremonitor/contents/scripts/sensors.py", sensors)
