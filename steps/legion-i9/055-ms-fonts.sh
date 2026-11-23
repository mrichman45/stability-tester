# title: Microsoft fonts for Office documents
# section: Microsoft fonts
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  pacman -Q ttf-ms-win11-auto >/dev/null 2>&1 || { echo "ttf-ms-win11-auto isn't installed"; return 1; }
  return 0
}

apply() {
@aur ttf-ms-win11-auto
}
