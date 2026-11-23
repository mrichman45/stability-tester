# title: pacman checks for free space before updating
# section: Config files pacman left as .pacnew
. "$(dirname "${BASH_SOURCE[0]}")/_lib.sh"

check() {
  grep -q '^CheckSpace' /etc/pacman.conf || { echo "pacman doesn't check for free space before an update"; return 1; }
}

apply() {
sudo sed -i '/^#UseDelta/d; s/^#CheckSpace/CheckSpace/' /etc/pacman.conf
}
