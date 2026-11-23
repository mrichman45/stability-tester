# title: CachyOS login screen and desktop theme
# section: 8. Extra software and the CachyOS look
# default: on
# manual: Pick the CachyOS theme in System Settings > Colors & Themes > Login Screen (SDDM), and CachyOS Nord under Global Theme.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs cachyos-themes-sddm sddm-kcm cachyos-nord-kde-theme-git || return 1
  return 0
}

apply() {
sudo pacman -S --needed cachyos-themes-sddm sddm-kcm cachyos-nord-kde-theme-git
}
