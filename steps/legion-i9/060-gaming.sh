# title: Gaming stack: Steam, Heroic, Lutris, MangoHud, proton-cachyos, GE-Proton
# section: 6. Gaming
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs cachyos-gaming-meta cachyos-gaming-applications proton-ge-custom-bin umu-launcher || return 1
  return 0
}

apply() {
sudo pacman -S --needed cachyos-gaming-meta cachyos-gaming-applications proton-ge-custom-bin umu-launcher
}
