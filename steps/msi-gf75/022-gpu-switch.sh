# title: Game GPU switcher (Meta+Alt+G: auto, Intel, NVIDIA)
# section: Pick the GPU per game (Game GPU switcher)
# after: Remove any prime-run or gpu-run launch options from Steam games; Steam passes the choice on now.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_files ~/.local/bin/intel-run ~/.local/bin/gpu-run ~/.local/bin/steam-gpu ~/.local/bin/steam-restart ~/.local/bin/gpu-mode-cycle ~/.config/gpu-mode || return 1
  [ ! -e /usr/share/applications/steam.desktop ] || grep -qs 'steam-gpu' ~/.local/share/applications/steam.desktop || { echo "Steam's menu entry doesn't start through steam-gpu"; return 1; }
}

apply() {
bash $R/install-gpu-switch.sh
}
