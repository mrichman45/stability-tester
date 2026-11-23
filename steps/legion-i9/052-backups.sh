# title: Kup backups
# section: Backups of your files
# default: on
# manual: Add a backup plan in System Settings > Backups.
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs kup bup rsync || return 1
  return 0
}

apply() {
sudo pacman -S --needed kup bup rsync
}
