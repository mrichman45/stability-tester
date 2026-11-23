# title: Waywallen starts at login, on the Intel GPU
# section: 16. Waywallen at login (KDE Plasma)
# when: command -v waywallen
# manual: Right-click the desktop > Configure Desktop and Wallpaper > Wallpaper type: Waywallen > Apply.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  f=$(ls ~/.config/autostart/*waywallen*.desktop 2>/dev/null | head -n1)
  [ -n "$f" ] || { echo "Waywallen doesn't start at login"; return 1; }
  grep -q '^Exec=.*intel-run waywallen' "$f" || { echo "Waywallen renders on the RTX (keeps it awake, costs battery)"; return 1; }
}

apply() {
mkdir -p ~/.config/autostart
f=$(ls ~/.config/autostart/*waywallen*.desktop 2>/dev/null | head -n1); [ -n "$f" ] || { cp /usr/share/applications/*waywallen*.desktop ~/.config/autostart/; }; true
sed -i "s|^Exec=waywallen\$|Exec=/usr/bin/env __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/50_mesa.json $HOME/.local/bin/intel-run waywallen|" ~/.config/autostart/*waywallen*.desktop
}
