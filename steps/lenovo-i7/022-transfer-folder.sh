# title: Transfer folder shared with Windows
# section: Moving files from a flash drive into Windows
# when: pacman -Q winboat
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  [ -d ~/Transfer ] || { echo "there's no ~/Transfer folder for moving files into Windows"; return 1; }
}

apply() {
mkdir -p ~/Transfer
}
