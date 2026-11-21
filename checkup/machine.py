"""Work out which of our laptops this is, using machines.json."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .util import read

PACKAGED = Path("/usr/share/checkup/machines.json")
REPO = Path(__file__).resolve().parent.parent / "machines.json"


@dataclass
class Machine:
    id: str
    label: str
    cpu: str
    product: str
    checks: list = field(default_factory=list)
    detected_by: str = ""
    health: list = field(default_factory=list)   # laptop health tests (checkup/health.py)
    limits: dict = field(default_factory=dict)   # {"cpu": °C, "gpu": °C} warning thresholds
    guide: str = "guides/README.md"              # this laptop's guide, relative to the repo


def profiles():
    """All laptop profiles. The copy in the repo clone (~/stability-tester) wins, so edits there apply."""
    for path in (Path.home() / "stability-tester/machines.json", REPO, PACKAGED):
        if path.exists():
            data = json.loads(path.read_text())
            return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def cpu_model():
    for line in read("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def product_name():
    parts = [read(f"/sys/class/dmi/id/{f}").strip() for f in ("sys_vendor", "product_family", "product_name", "product_version")]
    return " ".join(p for p in parts if p) or "unknown"


def detect(override=""):
    """Returns a Machine; id 'unknown' means the app should ask which laptop this is."""
    cpu, product = cpu_model(), product_name()
    profs = profiles()

    def make(mid, how):
        p = profs[mid]
        return Machine(mid, p.get("label", mid), cpu, product, list(p.get("checks", [])), how,
                       list(p.get("health", [])), dict(p.get("limits", {})), p.get("guide", "guides/README.md"))

    if override == "none":   # "none of these": general checks only
        return Machine("unknown", "Other computer", cpu, product, ["updates", "reboot", "dns"], "your choice")
    # Laptops are recognised by hardware only, so no names need to be stored in the repo.
    if override in profs:
        return make(override, "your choice")
    for mid, p in profs.items():
        if any(h.lower() in cpu.lower() for h in p.get("cpu", [])):
            return make(mid, "processor")
    for mid, p in profs.items():
        if any(h.lower() in product.lower() for h in p.get("product", [])):
            return make(mid, "laptop model")
    return Machine("unknown", "Unrecognised computer", cpu, product, ["updates", "reboot", "dns"], "")
