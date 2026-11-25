#!/bin/bash
# 4-legion.sh — phase 4 of the Gentoo guide. Run as yourself (it asks for sudo) on the new
# Gentoo, after logging in to Plasma.
#
# Your home folder came over from CachyOS, so ~/.local/bin (gpu-run, steam-gpu, legion-session,
# ...), your user services, MangoHud and the gaming settings are already in place. This puts
# back the system-wide half: legion-system and legion-power, the module and NTFS-repair boot
# services, legiond's settings, and the bits that differ on Gentoo. Safe to run again.
set -euo pipefail
[ "$(id -u)" != 0 ] || { echo "Run this as yourself, not with sudo."; exit 1; }
[ -f /etc/gentoo-release ] || { echo "This is for the new Gentoo install."; exit 1; }
REPO=${REPO:-$HOME/.local/src/stability-tester}
L="$REPO/tools/legion"
[ -f "$L/manifest.json" ] || { echo "Can't find $L. Set REPO=/path/to/stability-tester."; exit 1; }
say() { printf '\n== %s\n' "$*"; }
warn() { printf '!! %s\n' "$*"; }

say "1/7 Tools the Legion scripts need"
missing=""
for c in pactl jq kdialog notify-send powerprofilesctl ntfsfix prime-run sensors smartctl; do
  command -v "$c" >/dev/null || missing+=" $c"
done
if [ -n "$missing" ]; then
  warn "Missing:$missing"
  echo "Find their packages with: e-file <command>   (from app-portage/pfl), or ask me."
  echo "Most are installed by 3-desktop.sh; smartctl is sys-apps/smartmontools."
fi

say "2/7 Which drive is the NTFS data drive"
NTFS_UUID=$(sed -nE 's/^UUID=([^[:space:]]+)[[:space:]]+\/mnt\/ntfsdrive[[:space:]].*/\1/p' /etc/fstab | head -1)
if [ -z "$NTFS_UUID" ]; then
  lsblk -o NAME,SIZE,FSTYPE,UUID,LABEL | grep -i ntfs || true
  read -rp "UUID of the NTFS data drive (from the list above): " NTFS_UUID
fi
echo "NTFS data drive: $NTFS_UUID"

say "3/7 legion-system, legion-power and their boot services (from the repo)"
python3 - "$L" "$USER" "$NTFS_UUID" <<'PY' > /tmp/legion-root-files.txt
import json, sys
src, user, ntfs = sys.argv[1:4]
m = json.load(open(f"{src}/manifest.json"))
for f in m["files"]:
    if f["root"]:
        print(f["src"], f["dest"], f["mode"], f.get("after", ""), sep="\t")
PY
while IFS=$'\t' read -r name dest mode after; do
  tmp=$(mktemp)
  sed -e "s/__USER__/$USER/g" -e "s/__NTFS_UUID__/$NTFS_UUID/g" "$L/$name" > "$tmp"
  sudo install -Dm"$mode" "$tmp" "$dest"
  rm -f "$tmp"
  echo "installed $dest"
  if [ -n "$after" ]; then echo "running: $after"; eval "$after"; fi
done < /tmp/legion-root-files.txt
rm -f /tmp/legion-root-files.txt

say "4/7 Your own Legion files (already in your home folder; filling any gaps)"
python3 - "$L" <<'PY' > /tmp/legion-user-files.txt
import json, sys
m = json.load(open(f"{sys.argv[1]}/manifest.json"))
for f in m["files"]:
    if not f["root"]:
        print(f["src"], f["dest"], f["mode"], sep="\t")
PY
while IFS=$'\t' read -r name dest mode; do
  dest=${dest/#\~/$HOME}
  if [ -e "$dest" ]; then echo "kept $dest"; continue; fi
  mkdir -p "$(dirname "$dest")"
  sed -e "s/__USER__/$USER/g" -e "s/__NTFS_UUID__/$NTFS_UUID/g" "$L/$name" > "$dest"
  chmod "$mode" "$dest"
  echo "installed $dest"
done < /tmp/legion-user-files.txt
rm -f /tmp/legion-user-files.txt

say "5/7 legiond: fan presets on, its CPU and GPU control off"
if [ -d /usr/share/legion_linux ] && [ ! -f /etc/legion_linux/legiond.ini ]; then
  sudo mkdir -p /etc/legion_linux && sudo cp -rn /usr/share/legion_linux/. /etc/legion_linux/
fi
if [ -f /etc/legion_linux/legiond.ini ]; then
  sudo sed -i -E 's/^(\s*cpu_control\s*=).*/\1 false/; s/^(\s*gpu_control\s*=).*/\1 false/' /etc/legion_linux/legiond.ini
else
  warn "No /etc/legion_linux/legiond.ini: is sys-firmware/lenovolegionlinux installed (3-desktop.sh, step 7)?"
fi

say "6/7 Turning services on and off (as on CachyOS)"
sudo systemctl daemon-reload
for u in $(python3 -c "import json;print(' '.join(json.load(open('$L/manifest.json'))['enable']))"); do
  if systemctl list-unit-files "$u" --no-legend | grep -q .; then sudo systemctl enable --now "$u"; else warn "$u doesn't exist here (skipped)"; fi
done
for u in $(python3 -c "import json;print(' '.join(json.load(open('$L/manifest.json'))['disable']))"); do
  systemctl list-unit-files "$u" --no-legend | grep -q . && sudo systemctl disable --now "$u" || true
done
systemctl --user daemon-reload
for u in $(python3 -c "import json;print(' '.join(json.load(open('$L/manifest.json'))['enable_user']))"); do
  systemctl --user enable --now "$u" || warn "couldn't start $u"
done

say "7/7 Gentoo differences"
# Your PipeWire noise filters point at Arch's plugin path; Gentoo keeps 64-bit plugins in lib64.
# A link makes the same config files work on both while CachyOS is still around.
if [ -e /usr/lib64/ladspa/librnnoise_ladspa.so ] && [ ! -e /usr/lib/ladspa/librnnoise_ladspa.so ]; then
  sudo mkdir -p /usr/lib/ladspa
  sudo ln -s /usr/lib64/ladspa/librnnoise_ladspa.so /usr/lib/ladspa/librnnoise_ladspa.so
  echo "linked the noise-suppression plugin where your PipeWire configs expect it"
fi
systemctl --user restart pipewire pipewire-pulse wireplumber 2>/dev/null || true

say "Checks"
systemctl is-active legion-system && echo "legion-system: running" || warn "legion-system isn't running: journalctl -t legion-system -n 20"
systemctl --user is-active legion-session && echo "legion-session: running" || warn "legion-session isn't running: journalctl --user -t legion-session -n 20"
lsmod | grep -q legion_laptop && echo "Legion module: loaded" || warn "legion_laptop isn't loaded: sudo modprobe legion_laptop; dmesg | tail"
echo "GPU for games right now: $(~/.local/bin/gpu-run --which 2>/dev/null || echo '?')"
cat /sys/firmware/acpi/platform_profile 2>/dev/null | sed 's/^/Power mode: /' || true

say "Phase 4 done"
echo "Next: the guide's 'Finishing' section (Secure Boot check, then removing CachyOS when you're happy)."
