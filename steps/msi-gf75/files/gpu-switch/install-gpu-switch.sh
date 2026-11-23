#!/usr/bin/env bash
# Game GPU switcher for the MSI GF75 Thin on CachyOS / KDE Plasma 6.
# Installs intel-run, gpu-run, gpu-mode-cycle, steam-gpu and steam-restart,
# makes the Steam shortcut start Steam through gpu-run (no per-game launch options),
# and binds Meta+Alt+G to cycle the mode.
# Run with:  bash install-gpu-switch.sh
set -euo pipefail

BIN="$HOME/.local/bin"
APPS="$HOME/.local/share/applications"
AUTOSTART="$HOME/.config/autostart"
SRC_DESKTOP="${STEAM_DESKTOP_SRC:-/usr/share/applications/steam.desktop}"
mkdir -p "$BIN" "$APPS" "$HOME/.config"

# --- intel-run: run a program on the Intel GPU ---------------------------------
cat > "$BIN/intel-run" <<'EOF'
#!/bin/sh
export VK_LOADER_DRIVERS_SELECT='*intel*'
export __NV_PRIME_RENDER_OFFLOAD=0
export __VK_LAYER_NV_optimus=non_NVIDIA_only
export __GLX_VENDOR_LIBRARY_NAME=mesa
export DXVK_FILTER_DEVICE_NAME=Intel
export VKD3D_FILTER_DEVICE_NAME=Intel
exec "$@"
EOF

# --- gpu-run: pick the GPU from ~/.config/gpu-mode -------------------------------
cat > "$BIN/gpu-run" <<'EOF'
#!/bin/sh
# Modes: auto (NVIDIA on AC, Intel on battery), nvidia, intel
# "gpu-run --which" prints the GPU the current mode resolves to.
mode=$(cat "$HOME/.config/gpu-mode" 2>/dev/null || echo auto)
if [ "$mode" = auto ]; then
  mode=intel
  for ps in /sys/class/power_supply/*; do
    [ "$(cat "$ps/type" 2>/dev/null)" = Mains ] && [ "$(cat "$ps/online" 2>/dev/null)" = 1 ] && mode=nvidia
  done
fi
[ "$mode" = intel ] || mode=nvidia
if [ "${1:-}" = --which ]; then
  echo "$mode"
  exit 0
fi
if [ "$mode" = intel ]; then
  exec "$HOME/.local/bin/intel-run" "$@"
else
  exec prime-run "$@"
fi
EOF

# --- steam-gpu: start Steam on the chosen GPU and remember which one ---------------
cat > "$BIN/steam-gpu" <<'EOF'
#!/bin/sh
# Already running: just hand the request (e.g. a store link) to the running Steam.
if pgrep -x steam >/dev/null; then
  exec /usr/bin/steam "$@"
fi
"$HOME/.local/bin/gpu-run" --which > "$HOME/.config/gpu-mode-steam"
exec "$HOME/.local/bin/gpu-run" /usr/bin/steam "$@"
EOF

# --- steam-restart: close Steam and reopen it on the current mode -----------------
cat > "$BIN/steam-restart" <<'EOF'
#!/bin/sh
if pgrep -x steam >/dev/null; then
  /usr/bin/steam -shutdown >/dev/null 2>&1
  i=0
  while pgrep -x steam >/dev/null && [ "$i" -lt 60 ]; do
    sleep 1
    i=$((i + 1))
  done
  if pgrep -x steam >/dev/null; then
    notify-send -a "GPU mode" -i dialog-warning "Steam didn't close" "Close it yourself, then start it again."
    exit 1
  fi
fi
setsid -f "$HOME/.local/bin/steam-gpu" >/dev/null 2>&1
notify-send -a "GPU mode" -i video-display "Steam restarting on: $("$HOME/.local/bin/gpu-run" --which)"
EOF

# --- gpu-mode-cycle: auto -> intel -> nvidia -> auto, with a notification -------
cat > "$BIN/gpu-mode-cycle" <<'EOF'
#!/bin/sh
f="$HOME/.config/gpu-mode"
cur=$(cat "$f" 2>/dev/null || echo auto)
case "$cur" in
  auto) next=intel ;;
  intel) next=nvidia ;;
  *) next=auto ;;
esac
mkdir -p "$HOME/.config"
echo "$next" > "$f"
body=""
if pgrep -x steam >/dev/null; then
  running=$(cat "$HOME/.config/gpu-mode-steam" 2>/dev/null)
  [ "$running" = "$("$HOME/.local/bin/gpu-run" --which)" ] || body="Restart Steam to apply (Game GPU widget)."
fi
notify-send -a "GPU mode" -i video-display "Games will use: $next" "$body"
EOF

chmod +x "$BIN/intel-run" "$BIN/gpu-run" "$BIN/steam-gpu" "$BIN/steam-restart" "$BIN/gpu-mode-cycle"
[ -f "$HOME/.config/gpu-mode" ] || echo auto > "$HOME/.config/gpu-mode"

# --- Steam shortcut: start Steam through steam-gpu ----------------------------------
retarget() {  # rewrite every Exec= line so it starts with steam-gpu
  sed -E "s#^Exec=(env( [A-Za-z_][A-Za-z0-9_]*=[^ ]*)+ )?(prime-run )?(/usr/bin/)?steam(-runtime)?([ ]|\$)#Exec=$BIN/steam-gpu\6#" "$1"
}
stamp=$(date +%Y%m%d-%H%M%S)
if [ -f "$APPS/steam.desktop" ]; then
  cp "$APPS/steam.desktop" "$APPS/steam.desktop.bak-$stamp"
fi
if [ -f "$SRC_DESKTOP" ]; then
  retarget "$SRC_DESKTOP" > "$APPS/steam.desktop.new"
else
  cat > "$APPS/steam.desktop.new" <<EOF
[Desktop Entry]
Name=Steam
Comment=Application for managing and playing games on Steam
Exec=$BIN/steam-gpu %U
Icon=steam
Terminal=false
Type=Application
Categories=Network;FileTransfer;Game;
MimeType=x-scheme-handler/steam;x-scheme-handler/steamlink;
EOF
fi
mv "$APPS/steam.desktop.new" "$APPS/steam.desktop"

if [ -f "$AUTOSTART/steam.desktop" ]; then
  cp "$AUTOSTART/steam.desktop" "$AUTOSTART/steam.desktop.bak-$stamp"
  retarget "$AUTOSTART/steam.desktop.bak-$stamp" > "$AUTOSTART/steam.desktop"
fi

# --- KDE shortcut: Meta+Alt+G runs gpu-mode-cycle -------------------------------
cat > "$APPS/gpu-mode-cycle.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Cycle game GPU
Exec=$BIN/gpu-mode-cycle
Icon=video-display
NoDisplay=true
X-KDE-GlobalAccel-CommandShortcut=true
EOF

if command -v kwriteconfig6 >/dev/null; then
  kwriteconfig6 --file kglobalshortcutsrc --group services --group gpu-mode-cycle.desktop \
    --key _launch "Meta+Alt+G"
  systemctl --user restart plasma-kglobalaccel.service 2>/dev/null || true
fi
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true

echo
echo "Installed to $BIN: intel-run, gpu-run, steam-gpu, steam-restart, gpu-mode-cycle"
echo "Steam shortcut now starts Steam through gpu-run: $APPS/steam.desktop"
grep '^Exec=' "$APPS/steam.desktop" | head -3
echo "Current mode: $(cat "$HOME/.config/gpu-mode") -> $("$BIN/gpu-run" --which)"
echo
echo "Next: run  ~/.local/bin/steam-restart  so Steam picks this up,"
echo "then remove the prime-run / gpu-run launch options from your games."
echo "Meta+Alt+G cycles auto -> intel -> nvidia (log out and back in if it does nothing)."
