# title: Everyday apps: LibreOffice, Discord, Spotify
# section: 12. Everyday apps
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs libreoffice-fresh discord spotify-launcher || return 1
  return 0
}

apply() {
sudo pacman -S --needed libreoffice-fresh discord spotify-launcher
}
