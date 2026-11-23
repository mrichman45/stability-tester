#!/usr/bin/env bash
# The Convergence mode picker: Seamless Co-op or Solo
set -euo pipefail

INSTALL_DIR="$HOME/Games/ConvergenceER/ConvergenceER"   # Convergence install folder
LAUNCHER_DIR="$HOME/Applications"                        # where the AppImage lives
# always the RTX, even when section 3 has put other apps on Intel:
PRIME="env -u VK_LOADER_DRIVERS_SELECT -u DXVK_FILTER_DEVICE_NAME -u VKD3D_FILTER_DEVICE_NAME prime-run"

ON="$INSTALL_DIR/SeamlessCoop"
OFF="$INSTALL_DIR/SeamlessCoop.off"
LAUNCHER="$(ls "$LAUNCHER_DIR"/*[Cc]onvergence*.AppImage 2>/dev/null | head -n1 || true)"

msg() {
  if command -v kdialog >/dev/null; then kdialog --title "The Convergence" --error "$1"
  elif command -v zenity >/dev/null; then zenity --error --title="The Convergence" --text="$1"
  else echo "ERROR: $1" >&2
  fi
}

mode="${1:-}"
if [[ -z "$mode" ]]; then
  if command -v kdialog >/dev/null; then
    mode=$(kdialog --title "The Convergence" --radiolist "Start which session?" \
      coop "Seamless Co-op" on \
      solo "Solo (no Seamless)" off) || exit 0
  elif command -v zenity >/dev/null; then
    mode=$(zenity --list --radiolist --title="The Convergence" --text="Start which session?" \
      --column="" --column="mode" --column="Session" \
      TRUE coop "Seamless Co-op" FALSE solo "Solo (no Seamless)" \
      --hide-column=2 --print-column=2) || exit 0
  else
    read -rp "Start with Seamless Co-op? [y/N] " a
    [[ $a =~ ^[Yy] ]] && mode=coop || mode=solo
  fi
fi

if pgrep -fi "eldenring.exe" >/dev/null; then
  msg "Elden Ring is still running. Close it before switching modes."
  exit 1
fi

if [[ -d "$ON" && -d "$OFF" ]]; then
  msg "Both SeamlessCoop and SeamlessCoop.off exist in $INSTALL_DIR. Keep the newer one, delete the other, then try again."
  exit 1
fi

case "$mode" in
  coop)
    [[ -d "$OFF" ]] && mv "$OFF" "$ON"
    if [[ ! -f "$ON/ersc.dll" ]]; then
      msg "Seamless files not found. Expected: $ON/ersc.dll"
      exit 1
    fi
    ;;
  solo)
    [[ -d "$ON" ]] && mv "$ON" "$OFF"
    ;;
  *)
    msg "Unknown mode '$mode'. Use coop or solo."
    exit 1
    ;;
esac

if [[ -z "$LAUNCHER" ]]; then
  msg "Convergence AppImage not found in $LAUNCHER_DIR."
  exit 1
fi

echo "Mode: $mode — starting $LAUNCHER"
exec $PRIME "$LAUNCHER"
