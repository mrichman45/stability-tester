"""Laptop health tests: does each fix from the guide still WORK (not just configured)?

Run after updates. A failure means an update probably undid or broke a fix, and comes with a
'reapply' fix. Which tests run on which laptop is set in machines.json ("health").
"""

import os
import shutil
import tempfile
import time
from pathlib import Path

from . import fixers
from .checks import FAIL, OK, SKIP, WARN, Check, Fix, Result, WINDOWS_MOUNT, windows_partition
from .util import HOME, pkg_version, read, run, unit_state, which


def h_nvidia(ctx):
    rc, pci, _ = run(["lspci"], timeout=10)
    if rc == 0 and "nvidia" not in pci.lower():
        return None   # this laptop has no NVIDIA graphics
    if not which("nvidia-smi"):
        return Result(FAIL, "The NVIDIA driver isn't installed or nvidia-smi is missing.",
                      Fix("Reinstalled the NVIDIA driver tools", ["sudo pacman -S --needed nvidia-utils lib32-nvidia-utils"],
                          after="Reboot afterwards."))
    rc, out, err = run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"], timeout=20)
    text = out + err
    if "mismatch" in text.lower():
        return Result(FAIL, "Driver/library version mismatch: an NVIDIA update was installed but the old driver is still loaded.",
                      manual="Reboot. If it persists after rebooting, use 'NVIDIA driver versions match' in My Setup.")
    if rc != 0:
        return Result(FAIL, "The NVIDIA driver isn't loaded: " + text.strip()[:200],
                      Fix("Reinstalled the NVIDIA driver", ["sudo pacman -S nvidia-utils lib32-nvidia-utils"],
                          after="Reboot afterwards."))
    name = out.strip().splitlines()[0] if out.strip() else "NVIDIA GPU"
    if which("glxinfo"):
        env = dict(os.environ, __NV_PRIME_RENDER_OFFLOAD="1", __GLX_VENDOR_LIBRARY_NAME="nvidia")
        rc2, gl, _ = run(["glxinfo", "-B"], timeout=20, env=env)
        if rc2 == 0 and "NVIDIA" not in gl:
            return Result(FAIL, f"{name} is loaded, but apps can't draw on it (they fall back to the Intel graphics).",
                          Fix("Reinstalled the NVIDIA OpenGL libraries", ["sudo pacman -S nvidia-utils lib32-nvidia-utils"],
                              after="Reboot afterwards."))
    return Result(OK, f"{name.split(',')[0]} works (driver {name.split(',')[-1].strip()}).")


def h_docker(ctx):
    if not which("docker"):
        return Result(FAIL, "Docker isn't installed.", Fix("Reinstalled Docker", [
            "sudo pacman -S --needed docker", "sudo systemctl enable --now docker.service"]))
    rc, out, err = run(["docker", "run", "--rm", "hello-world"], timeout=180)
    if rc == 0 and "Hello from Docker" in out:
        return Result(OK, "Docker ran a test container.")
    text = (out + err).lower()
    if "permission denied" in text:
        return Result(FAIL, "No permission to use Docker (group membership not active).",
                      Fix("Re-added you to the docker group", [f"sudo usermod -aG docker {os.environ.get('USER', '$USER')}"],
                          after="Log out and back in."))
    if "cannot connect" in text or "is the docker daemon running" in text:
        return Result(FAIL, "The Docker service isn't running.", Fix("Restarted Docker", [
            "sudo systemctl enable --now docker.service", "sudo systemctl restart docker.service"]))
    if "pull" in text or "dial tcp" in text or "lookup" in text:
        return Result(WARN, "Docker works, but couldn't download the test image (no internet?).")
    return Result(FAIL, "Docker couldn't run a container: " + (err or out).strip()[:200],
                  Fix("Restarted Docker", ["sudo systemctl restart docker.service"]))


def h_vlc(ctx):
    if not which("cvlc"):
        return None
    if not which("ffmpeg"):
        return Result(SKIP, "ffmpeg isn't installed, so a test video can't be made.")
    with tempfile.TemporaryDirectory() as d:
        clip = Path(d) / "test.mp4"
        rc, _, err = run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240",
                          "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)], timeout=60)
        if rc != 0:
            return Result(SKIP, "Couldn't make an h264 test video.")
        rc, out, err = run(["cvlc", "--play-and-exit", "--vout=dummy", "--aout=dummy", "--no-video-title-show",
                            "-v", str(clip)], timeout=60)
    text = out + err
    if "not supported" in text.lower() or "could not decode" in text.lower():
        return Result(FAIL, "VLC can't decode h264 any more (an update probably split off its plugins again).",
                      Fix("Reinstalled VLC's plugins", ["sudo pacman -S --needed vlc-plugins-all", "rm -rf ~/.cache/vlc"]))
    return Result(OK, "VLC decoded an h264 test video.")


def h_fastfetch(ctx):
    if not which("fish"):
        return None
    config = HOME / ".config/fish/config.fish"
    rc, out, _ = run(["fish", "-c", "functions fish_greeting"], timeout=20)
    if rc == 0 and "fastfetch" in out and (not which("fastfetch") or run(["fastfetch", "--pipe", "--logo", "none"], timeout=20)[0] == 0):
        return Result(OK, "Opening a terminal shows fastfetch.")
    text = read(config)
    new = fixers.fish_fastfetch_fix(text)

    def apply():
        config.parent.mkdir(parents=True, exist_ok=True)
        if config.exists():
            config.with_name(f"config.fish.checkup-backup-{time.strftime('%Y%m%d-%H%M%S')}").write_text(text)
        config.write_text(new)
        return f"Rewrote {config}."

    return Result(FAIL, "fish's greeting no longer runs fastfetch.", Fix(
        "Restored the fastfetch greeting", ["sudo pacman -S --needed fastfetch"], python=apply,
        preview=f"New {config}:\n\n{new}"))


def h_windows_drive(ctx):
    if not windows_partition(ctx):
        return Result(SKIP, "No Windows (NTFS) partition found.")
    try:
        entries = os.listdir(WINDOWS_MOUNT)
    except OSError as e:
        return Result(FAIL, f"Can't read {WINDOWS_MOUNT}: {e.strerror}.",
                      manual="Use 'Windows drive mounts at boot' in My Setup; it detects a dirty drive and repairs fstab.")
    if not entries:
        return Result(FAIL, f"{WINDOWS_MOUNT} is empty: the drive isn't mounted.",
                      Fix("Mounted the Windows drive", [f"sudo mkdir -p {WINDOWS_MOUNT}", "sudo mount -a"]))
    return Result(OK, f"The Windows drive is readable ({len(entries)} items at the top level).")


def h_camera(ctx):
    nodes = sorted(Path("/sys/class/video4linux").glob("video*"))
    if not nodes:
        return Result(WARN, "No camera detected.", manual="Slide the camera switch on the right side of the laptop to on.")
    if not which("v4l2-ctl"):
        return Result(OK, "Camera detected (install v4l-utils to test capturing a frame).")
    dev = f"/dev/{nodes[0].name}"
    rc, out, err = run(["v4l2-ctl", "-d", dev, "--stream-mmap", "--stream-count=3", "--stream-to=/dev/null"], timeout=30)
    if rc == 0:
        return Result(OK, "The camera captured test frames.")
    if "busy" in (out + err).lower():
        return Result(WARN, "The camera is in use by another app, so it couldn't be tested.")
    return Result(FAIL, "The camera is detected but couldn't capture: " + (err or out).strip()[:150],
                  manual="Close other camera apps, toggle the camera switch off and on, or reboot.")


def h_webcam_service(ctx):
    if not pkg_version("kcm-webcam"):
        return None
    enabled, active = unit_state("webcam-settings.service", user=True)
    if active == "active":
        return Result(OK, "The webcam settings service is running.")
    return Result(FAIL, f"The webcam settings service is {active}.", Fix(
        "Restarted the webcam settings service",
        ["systemctl --user daemon-reload", "systemctl --user enable webcam-settings.service",
         "systemctl --user restart webcam-settings.service"]))


def h_wifi(ctx):
    if not which("nmcli"):
        return None
    rc, out, _ = run(["nmcli", "-t", "-f", "TYPE,STATE", "device"], timeout=10)
    states = [l.split(":", 1)[1] for l in out.splitlines() if l.startswith("wifi:")]
    if not states:
        return Result(FAIL, "No Wi-Fi adapter found (the driver may not have loaded after an update).",
                      manual="Reboot. If Wi-Fi is still missing, boot the previous kernel from the boot menu.")
    if any(s == "connected" for s in states):
        return Result(OK, "Wi-Fi adapter present and connected.")
    return Result(WARN, "Wi-Fi adapter present but not connected.")


HEALTH = [
    Check("nvidia", "NVIDIA graphics work", "nvidia-mismatch", h_nvidia),
    Check("wifi", "Wi-Fi works", "dns", h_wifi),
    Check("docker", "Docker runs containers", "docker", h_docker),
    Check("vlc", "VLC plays h264", "vlc", h_vlc),
    Check("fastfetch", "Terminal greeting works", "fastfetch", h_fastfetch),
    Check("windows-drive", "Windows drive readable", "ntfs-automount", h_windows_drive),
    Check("camera", "Webcam captures", "webcam", h_camera),
    Check("webcam-service", "Webcam settings service running", "kcm-webcam", h_webcam_service),
]


# Profile items that aren't about whether the profile works (pending updates are normal).
NOT_PROFILE_TESTS = {"updates"}


def run_health(ctx, wanted, progress=None, profile_checks=()):
    """Test that this laptop's profile works.

    For each item: the working-test from HEALTH if it's listed in `wanted` (machines.json "health")
    and applies here; otherwise the profile's own check from checks.py.
    Returns [(Check, Result)].
    """
    from .checks import CHECKS
    tests = {c.id: c for c in HEALTH if c.id in wanted}
    checks = {c.id: c for c in CHECKS
              if (c.id in profile_checks or c.id == "extras") and c.id not in NOT_PROFILE_TESTS}
    order = list(tests) + [i for i in checks if i not in tests]
    if any(i in checks for i in ("secure-boot", "windows-drive")):
        ctx.gather_root(True)

    def attempt(c):
        if progress:
            progress(c.title)
        try:
            return c.func(ctx)
        except Exception as e:
            return Result(WARN, f"Test couldn't run: {e}")

    out = []
    for i in order:
        c, r = tests.get(i), None
        if c:
            r = attempt(c)
        if r is None and i in checks:   # no working-test applies: fall back to the profile check
            c = checks[i]
            r = attempt(c)
        if r is not None:
            out.append((c, r))
    return out
