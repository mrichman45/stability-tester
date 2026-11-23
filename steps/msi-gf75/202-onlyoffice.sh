# title: OnlyOffice (for documents that must look exactly like Word)
# section: Word processor
# default: off
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  pacman -Q onlyoffice-bin >/dev/null 2>&1 || { echo "onlyoffice-bin isn't installed"; return 1; }
  return 0
}

apply() {
@aur onlyoffice-bin
}
