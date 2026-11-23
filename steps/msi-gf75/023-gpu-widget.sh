# title: Game GPU widget for the panel
# section: Pick the GPU per game (Game GPU switcher)
# manual: Add it to the panel: right-click the panel > Add Widgets > Game GPU.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  kpackagetool6 -t Plasma/Applet -l 2>/dev/null | grep -q "org.$USER.gpumode" || { echo "the Game GPU widget isn't installed"; return 1; }
}

apply() {
kpackagetool6 -t Plasma/Applet -u $R/gpu-mode-widget 2>/dev/null || kpackagetool6 -t Plasma/Applet -i $R/gpu-mode-widget
}
