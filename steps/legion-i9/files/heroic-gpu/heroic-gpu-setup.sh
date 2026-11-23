#!/usr/bin/env bash
# Makes every Heroic game start through game-gpu, so each game picks its GPU when it launches
# (the RTX on the charger, Intel on battery), while Heroic's own window stays on Intel.
# (Updated by Checkup from the guide: game-gpu instead of gpu-run, see section 3 "Heroic".)
#  - Game Defaults and every existing game get ~/.local/bin/game-gpu as wrapper
#  - old prime-run / gpu-run / intel-run wrappers are removed
#  - "Force use of NVIDIA Optimus or AMD Dynamic Switchable Graphics GPU" is turned off (it would force the RTX)
# Run with:  bash heroic-gpu-setup.sh        Undo: copy back the backup folder it prints.
set -euo pipefail

GPU_RUN="$HOME/.local/bin/game-gpu"
[ -x "$GPU_RUN" ] || { echo "game-gpu not found. Install the Legion services first."; exit 1; }

# Native install (CachyOS repo) or Flatpak
CFG=""
for d in "${HEROIC_CONFIG_DIR:-}" "$HOME/.config/heroic" "$HOME/.var/app/com.heroicgameslauncher.hgl/config/heroic"; do
  [ -n "$d" ] && [ -f "$d/config.json" ] && { CFG="$d"; break; }
done
[ -n "$CFG" ] || { echo "Heroic config not found. Open Heroic once, close it, and run this again."; exit 1; }

case "$CFG" in
  *com.heroicgameslauncher.hgl*)
    echo "Flatpak Heroic found: giving it access to ~/.local/bin so it can run game-gpu."
    flatpak override --user --filesystem="$HOME/.local/bin:ro" com.heroicgameslauncher.hgl || true ;;
esac

if pgrep -x heroic >/dev/null || pgrep -f "/opt/[Hh]eroic/|com\.heroicgameslauncher\.hgl" >/dev/null; then
  echo "Heroic is running. Quit it completely (tray icon > Quit) and run this again;"
  echo "otherwise it overwrites these settings when it closes."
  exit 1
fi

BACKUP="$CFG/backup-gpu-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
cp "$CFG/config.json" "$BACKUP/"
[ -d "$CFG/GamesConfig" ] && cp -r "$CFG/GamesConfig" "$BACKUP/"

python3 - "$CFG" "$GPU_RUN" <<'PY'
import json, os, sys, glob

cfg_dir, gpu_run = sys.argv[1], sys.argv[2]
OLD = ("prime-run", "gpu-run", "intel-run", "game-gpu")
PRIME_VARS = {"__NV_PRIME_RENDER_OFFLOAD", "__VK_LAYER_NV_optimus", "__GLX_VENDOR_LIBRARY_NAME",
              "VK_LOADER_DRIVERS_SELECT", "DXVK_FILTER_DEVICE_NAME", "VKD3D_FILTER_DEVICE_NAME"}

def fix(settings, label):
    wrappers = [w for w in settings.get("wrapperOptions") or []
                if isinstance(w, dict) and not any(o in str(w.get("exe", "")) for o in OLD)]
    settings["wrapperOptions"] = [{"exe": gpu_run, "args": ""}] + wrappers
    settings["nvidiaPrime"] = False
    env = settings.get("enviromentOptions") or []   # Heroic's own spelling
    clash = [e.get("key") for e in env if isinstance(e, dict) and e.get("key") in PRIME_VARS]
    note = f"  (check its environment variables: {', '.join(clash)} override the GPU choice)" if clash else ""
    print(f"  {label}{note}")

def load(path):
    with open(path) as f:
        return json.load(f)

def save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

print("Updated:")
main = os.path.join(cfg_dir, "config.json")
data = load(main)
data.setdefault("defaultSettings", {})
fix(data["defaultSettings"], "Game Defaults")
save(main, data)

for path in sorted(glob.glob(os.path.join(cfg_dir, "GamesConfig", "*.json"))):
    try:
        data = load(path)
    except (ValueError, OSError):
        print(f"  skipped {os.path.basename(path)} (unreadable)")
        continue
    changed = False
    for key, val in data.items():
        if key in ("version", "explicit") or not isinstance(val, dict):
            continue
        fix(val, f"game {key}")
        changed = True
    if changed:
        save(path, data)
PY

echo
echo "Backup of the old settings: $BACKUP"
echo "Start Heroic: each game now uses the GPU picked in the Game GPU widget or with Meta+Alt+G,"
echo "decided every time a game launches (no restart needed)."
