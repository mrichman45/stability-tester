# title: Gaming stack: Steam, Heroic, Lutris, MangoHud, proton-cachyos, GE-Proton
# section: 4. Gaming
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs cachyos-gaming-meta cachyos-gaming-applications umu-launcher || return 1
  pacman -Q proton-ge-custom-bin >/dev/null 2>&1 || ls -d ~/.steam/root/compatibilitytools.d/GE-Proton* ~/.local/share/Steam/compatibilitytools.d/GE-Proton* >/dev/null 2>&1 || { echo "GE-Proton isn't installed (package or ProtonUp-Qt)"; return 1; }
  return 0
}

apply() {
sudo pacman -S --needed cachyos-gaming-meta cachyos-gaming-applications umu-launcher proton-ge-custom-bin
}
