# title: KNotes sticky notes in their own window
# section: Sticky notes
# default: off
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs knotes || return 1
  return 0
}

apply() {
sudo pacman -S --needed knotes
}
