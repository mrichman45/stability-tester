# title: NTFS flash drives: repair tools and fallback driver
# section: NTFS flash drives (read and write)
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  need_pkgs ntfs-3g ntfsprogs || return 1
  return 0
}

apply() {
sudo pacman -S --needed ntfs-3g ntfsprogs
}
