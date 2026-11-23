# title: Google Chrome
# section: Chrome
# default: on
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  pacman -Q google-chrome >/dev/null 2>&1 || { echo "google-chrome isn't installed"; return 1; }
  return 0
}

apply() {
@aur google-chrome
}
