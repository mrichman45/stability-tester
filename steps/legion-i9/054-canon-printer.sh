# title: Canon UFR II printer driver
# section: Printers
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs libxml2-legacy || return 1
  pacman -Q cndrvcups-lb-bin >/dev/null 2>&1 || { echo "cndrvcups-lb-bin isn't installed"; return 1; }
  return 0
}

apply() {
sudo pacman -S --needed libxml2-legacy
@aur cndrvcups-lb-bin
}
