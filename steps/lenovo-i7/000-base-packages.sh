# title: Sound firmware, NTFS tools and update snapshots
# section: 7. First boot and checks
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs ntfsprogs sof-firmware snap-pac || return 1
  return 0
}

apply() {
sudo pacman -S --needed ntfsprogs sof-firmware snap-pac
}
